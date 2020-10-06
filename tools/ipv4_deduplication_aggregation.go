package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/c-robinson/iplib"
)

type Conf struct {
	str      string
	filePath string
}

var cfg Conf

func filter(s []string, f func(string) bool) []string {
	filtered := make([]string, 0)
	for _, v := range s {
		if f(v) {
			filtered = append(filtered, v)
		}
	}
	return filtered
}

func deduplicate(str []string) []string {
	var list []string

	if len(str) == 0 {
		return str
	}

	set := make(map[string]bool)
	for _, s := range str {
		set[s] = true
	}

	for k := range set {
		list = append(list, k)
	}

	return list
}

func getNetsFromInput(str string, path string) ([]string, error) {
	var list []string
	var err error = nil

	emptyStr := len(strings.TrimSpace(str)) == 0
	emptyPath := len(strings.TrimSpace(path)) == 0

	if emptyStr && emptyPath {
		err = fmt.Errorf("No input defined. Choose string or file input")
		return list, err
	}

	if !emptyStr && !emptyPath {
		err = fmt.Errorf("Both input options can not be used at the same time")
		return list, err
	}

	if !emptyStr {
		list = strings.Split(str, " ")
	} else {
		file, err := os.Open(path)
		if err != nil {
			err = fmt.Errorf("Can not open %s due to %v", path, err)
			return list, err
		}
		defer file.Close()

		reader := bufio.NewScanner(file)
		for reader.Scan() {
			list = append(list, reader.Text())
		}
	}

	list = filter(list, func(s string) bool {
		if len(strings.TrimSpace(s)) == 0 {
			return false
		}
		return true
	})

	list = deduplicate(list)
	return list, err
}

func getNetsFromString(str []string) ([]iplib.Net, error) {
	var list []iplib.Net
	var err error = nil

	for _, s := range str {
		_, n, e := iplib.ParseCIDR(s)
		if e != nil {
			err = fmt.Errorf("Bad IP network value: <%s>", s)
			return list, err
		}
		list = append(list, n)
	}
	// it is very important to keep network list sorted, then absorbing works properly
	sort.Sort(iplib.ByNet(list))
	return list, err
}

// absorbing small net by more large net
// if possible supernet is not real super net for given net, then
// adding the latter to absorbed and make it a new supernet for further nets checking
// otherwise do nothing, just skip the net due to one is absorbed by supernet
// 192.168.0.0/22, 192.168.0.0/24, 192.168.2.0/24 -> 192.168.0.0/22
// Note. Absorbed must be sorted, otherwise it can not work properly
func largeNetsAbsorbSmall(absorbed []iplib.Net, superNet iplib.Net, net iplib.Net) ([]iplib.Net, iplib.Net) {
	if !superNet.ContainsNet(net) {
		absorbed = append(absorbed, net)
		superNet = net
	}
	return absorbed, superNet
}

func lastIsNotGiven(sources []iplib.Net, nets ...iplib.Net) bool {
	last := sources[len(sources)-1]
	result := true
	for _, i := range nets {
		result = result && iplib.CompareNets(last, i) != 0
	}
	return result
}

// compares 2 nets if both have the same maximum closest supernet (e.i. mask - 1), then
// aggregate both to that supernet (merge to large),
// otherwise adding both
// 192.168.0.0/24, 192.168.1.0/24 -> 192.168.0.0/23
func smallMergedToLarge(aggregated []iplib.Net, net1 iplib.Net, net2 iplib.Net) ([]iplib.Net, iplib.Net) {
	net1SuperNet, _ := net1.Supernet(0)
	net2SuperNet, _ := net2.Supernet(0)
	prefixNet1, _ := net1.Mask.Size()
	prefixNet2, _ := net2.Mask.Size()

	// both have the same maximum closest supernet
	if prefixNet1 == prefixNet2 && iplib.CompareNets(net1SuperNet, net2SuperNet) == 0 {
		// if net1 is already in aggregated it has to be deleted if supernet is found
		if len(aggregated) != 0 && !lastIsNotGiven(aggregated, net1) {
			aggregated = aggregated[:len(aggregated)-1]
		}
		aggregated = append(aggregated, net1SuperNet)
		return aggregated, net2
	}

	if len(aggregated) == 0 {
		aggregated = append(aggregated, net1)
		// if last aggregated is not net1 or its maximum closest supernet, then adding one
	} else if lastIsNotGiven(aggregated, net1, net1SuperNet) {
		aggregated = append(aggregated, net1)
	}
	aggregated = append(aggregated, net2)

	return aggregated, net2
}

func aggregateNetworks(nets []iplib.Net) []iplib.Net {
	if len(nets) < 2 {
		return nets
	}
	sourceNets := nets
	netsNumber := len(nets)

	// absorb small networks by more large
	var absorbed []iplib.Net
	superNet := sourceNets[0]
	absorbed = append(absorbed, superNet)
	for _, net := range sourceNets[1:] {
		absorbed, superNet = largeNetsAbsorbSmall(absorbed, superNet, net)
	}
	// no more network for handling, one absorbed all
	if len(absorbed) == 1 {
		return absorbed
	}
	sourceNets = absorbed

	// merge closest networks
	// 192.168.0.0/24, 192.168.1.0/24 -> 192.168.0.0/23
	// 192.168.2.0/24, 192.168.3.0/24 -> 192.168.2.0/23
	// 192.168.0.0/23, 192.168.2.0/23 -> 192.168.0.0/22
	for {
		var mergeList []iplib.Net
		net1 := sourceNets[0]
		for _, net2 := range sourceNets[1:] {
			mergeList, net1 = smallMergedToLarge(mergeList, net1, net2)
		}
		sourceNets = mergeList
		// nothing changed e.i. no closest networks or all megred to one
		if len(sourceNets) == netsNumber || len(sourceNets) == 1 {
			break
		}
		netsNumber = len(sourceNets)
	}

	return sourceNets
}

func printResult(result []iplib.Net) {
	for _, i := range result {
		ip := i.IPNet.IP
		mask, _ := i.Mask.Size()
		fmt.Printf("%v/%v\n", ip, mask)
	}
}

func init() {
	description := `IPv4 networks aggregation.
App aggregates IPv4 networks from given string or file with following mechanic:
1. largest prefix absorbs all its subnet prefixes,
	e.g. 10.0.0.0/16 absorbs 10.0.0.0/22, 10.10.0.0/24 and so on;
2. prefixes of the same length merged to their supernet, which prefix is one less,
	e.g. 10.0.0.0/24, 10.0.1.0/24 will be merged to 10.0.0.0/23,
	but 10.0.0.0/24, 10.0.2.0/24 will not be merged to 10.0.0.0/22,
	because their closest supernets (/23) are different
	and all merging operations are handled only if supernet prefix is one less.
	`
	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "%s", description)
		flag.PrintDefaults()
	}
	//getting args
	flag.StringVar(&cfg.str, "string", "", "Quoted string of networks separated by space")
	flag.StringVar(&cfg.filePath, "filepath", "", "Path to file which contains networks separated by new line")
	flag.Parse()
}

func main() {
	exitCode := 0
	defer func() { os.Exit(exitCode) }()

	stringNets, err := getNetsFromInput(cfg.str, cfg.filePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		exitCode = 1
		return
	}

	nets, err := getNetsFromString(stringNets)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		exitCode = 1
		return
	}

	result := aggregateNetworks(nets)

	printResult(result)
}
