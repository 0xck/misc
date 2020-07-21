import argparse
from functools import reduce
from ipaddress import IPv4Network, ip_network
from sys import exit
from typing import (Any, Callable, Generic, List, NoReturn, Optional, Tuple,
                    TypeVar, Union)


Value = TypeVar("Value", List[str], List[IPv4Network])
Error = TypeVar("Error", str, Exception, contravariant=True)


class Result(Generic[Error, Value]):
    @property
    def value(self):
        raise NotImplementedError()

    @property
    def error(self):
        raise NotImplementedError()

    def fmap(self, func: Callable[[Value], Any]) -> "Result":
        raise NotImplementedError()

    def bind(self, func: Callable[[Value], Any]) -> "Result":
        raise NotImplementedError()

    def is_failure(self) -> bool:
        return isinstance(self, Failure)

    def is_success(self) -> bool:
        return isinstance(self, Success)


class Success(Result):
    @property
    def value(self) -> Union[List[str], List[IPv4Network]]:
        return self._value

    def __init__(self, value: Value):
        self._value: Union[List[str], List[IPv4Network]] = value

    def fmap(self, func: Callable[[Union[List[str], List[IPv4Network]]], Any]) -> "Success":
        assert callable(func), "fmap argument has to be callable"

        return Success(func(self._value))

    def bind(self, func: Callable[[Union[List[str], List[IPv4Network]]], Result[Error, Value]]) -> Result[Error, Value]:
        return func(self._value)


class Failure(Result):
    @property
    def error(self) -> Union[str, Exception]:
        return self._error

    def __init__(self, error: Error):
        self._error: Union[str, Exception] = error

    def fmap(self, _: Any) -> "Failure":
        return self

    def bind(self, _: Any) -> "Failure":
        return self


def get_nets_from_input(string: Optional[str], filepath: Optional[str]) -> Result[Error, List[str]]:
    source: List[str]
    error: str

    if string is None and filepath is None:
        return Failure("No input defined. Choose string or file input.")
    if string is not None and filepath is not None:
        return Failure("Both input options can not be used at the same time.")
    if string is not None:
        source = string.strip().split(" ")
        error = f"string: `{string}`"
    else:
        try:
            with open(filepath, "r") as file:  # type: ignore
                source = [l.strip() for l in file.readlines()]
                error = f"file: `{filepath}`"

        except (FileNotFoundError, PermissionError) as exc:
            return Failure(exc)

    lines: List[str] = [l for l in set(source) if l and l.isprintable()]

    return Success(lines) if lines else Failure(f"It seems given {error} does not contain a proper data.")


def get_net_from_str(nets: List[str]) -> Result[Error, List[IPv4Network]]:
    try:
        return Success(sorted(set(ip_network(n) for n in nets)))

    except ValueError as exc:
        return Failure(exc)


def aggregate_networks(nets: List[IPv4Network]) -> List[IPv4Network]:

    def large_absorb_small(aggregated_supernet: Tuple[List[IPv4Network], IPv4Network], net: IPv4Network) -> Tuple[List[IPv4Network], IPv4Network]:
        aggregated, supernet = aggregated_supernet

        if not net.subnet_of(supernet):  # type: ignore
            aggregated.append(net)
            supernet = net

        return aggregated, supernet

    def small_merge_large(aggregated_net1: Tuple[List[IPv4Network], IPv4Network], net2: IPv4Network) -> Tuple[List[IPv4Network], IPv4Network]:
        aggregated, net1 = aggregated_net1
        net1_supernet = net1.supernet()

        if net1.prefixlen == net2.prefixlen and net1_supernet == net2.supernet():
            aggregated.append(net1_supernet)
        else:
            if not aggregated:
                aggregated.append(net1)
            elif aggregated[-1] != net1 and aggregated[-1] != net1_supernet:
                aggregated.append(net1)
            aggregated.append(net2)

        return aggregated, net2

    if len(nets) == 1:
        return nets

    source_nets: List[IPv4Network] = nets
    nets_number: int = len(nets)

    while True:
        source_nets, _ = reduce(large_absorb_small, source_nets[1:], ([source_nets[0]], source_nets[0]))
        if len(source_nets) == 1:
            break

        merge_list: List[IPv4Network] = []
        source_nets, _ = reduce(small_merge_large, source_nets[1:], (merge_list, source_nets[0]))
        if len(source_nets) == nets_number or len(source_nets) == 1:
            break

        source_nets = sorted(source_nets)
        nets_number = len(source_nets)

    return source_nets


def get_aggregated(nets: List[IPv4Network]) -> List[str]:
    return [str(n) for n in aggregate_networks(nets)]


def print_result(nets: Result[Error, List[str]]) -> Union[None, NoReturn]:
    if nets.is_success():
        for n in nets.value:
            print(n)
    else:
        print(nets.error)
        exit(1)
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""IPv4 networks aggregation.
                                    App aggregates IPv4 networks from given string or file with following mechanic:
                                    1. largest prefix absorbs all its subnet prefixes,
                                      e.g. 10.0.0.0/16 absorbs 10.0.0.0/22, 10.10.0.0/24 and so on;
                                    2. prefixes of the same length merged to their supernet, which prefix is one less,
                                      e.g. 10.0.0.0/24, 10.0.1.0/24 will be merged to 10.0.0.0/23,
                                      but 10.0.0.0/24, 10.0.2.0/24 will not be merged to 10.0.0.0/22,
                                      because their closest supernets (/23) are different
                                      and all merging operations are handled only if supernet prefix is one less.""")
    parser.add_argument("-s", "--string",
                        help="Quoted string of networks separated by space")
    parser.add_argument("-f", "--filepath",
                        help="Path to file which contains networks separated by new line")
    opts = parser.parse_args()

    result = get_nets_from_input(opts.string, opts.filepath
                                ).bind(get_net_from_str
                                ).fmap(get_aggregated)
    print_result(result)
