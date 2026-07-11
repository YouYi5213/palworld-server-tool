package system

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"syscall"
)

type ResourceUsage struct {
	CpuPercent  float64 `json:"cpu_percent"`
	MemoryTotal uint64  `json:"memory_total"`
	MemoryUsed  uint64  `json:"memory_used"`
	MemoryPercent float64 `json:"memory_percent"`
	DiskTotal   uint64  `json:"disk_total"`
	DiskUsed    uint64  `json:"disk_used"`
	DiskPercent float64 `json:"disk_percent"`
}

func GetResourceUsage() (*ResourceUsage, error) {
	usage := &ResourceUsage{}

	memTotal, memAvail, err := getMemoryInfo()
	if err == nil {
		usage.MemoryTotal = memTotal
		usage.MemoryUsed = memTotal - memAvail
		if memTotal > 0 {
			usage.MemoryPercent = float64(usage.MemoryUsed) / float64(memTotal) * 100
		}
	}

	if runtime.GOOS == "linux" {
		cpu, err := getCPUPercent()
		if err == nil {
			usage.CpuPercent = cpu
		}
	}

	diskTotal, diskAvail, err := getDiskInfo()
	if err == nil {
		usage.DiskTotal = diskTotal
		usage.DiskUsed = diskTotal - diskAvail
		if diskTotal > 0 {
			usage.DiskPercent = float64(usage.DiskUsed) / float64(diskTotal) * 100
		}
	}

	return usage, nil
}

func getMemoryInfo() (total, avail uint64, err error) {
	if runtime.GOOS == "linux" {
		data, err := os.ReadFile("/proc/meminfo")
		if err != nil {
			return 0, 0, err
		}
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			fields := strings.Fields(line)
			if len(fields) < 2 {
				continue
			}
			switch fields[0] {
			case "MemTotal:":
				total, _ = strconv.ParseUint(fields[1], 10, 64)
			case "MemAvailable:":
				avail, _ = strconv.ParseUint(fields[1], 10, 64)
			}
		}
		if total > 0 && avail == 0 {
			avail = total
		}
		return total * 1024, avail * 1024, nil
	}
	return 0, 0, fmt.Errorf("unsupported platform")
}

func getCPUPercent() (float64, error) {
	data, err := os.ReadFile("/proc/stat")
	if err != nil {
		return 0, err
	}
	for _, line := range strings.Split(string(data), "\n") {
		if !strings.HasPrefix(line, "cpu ") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 5 {
			return 0, fmt.Errorf("unexpected cpu line format")
		}
		var total, idle uint64
		for i, f := range fields[1:] {
			val, _ := strconv.ParseUint(f, 10, 64)
			total += val
			if i == 3 {
				idle = val
			}
		}
		if total == 0 {
			return 0, nil
		}
		return float64(total-idle) / float64(total) * 100, nil
	}
	return 0, fmt.Errorf("cpu line not found in /proc/stat")
}

func getDiskInfo() (total, avail uint64, err error) {
	wd, err := os.Getwd()
	if err != nil {
		return 0, 0, err
	}
	var stat syscall.Statfs_t
	if err := syscall.Statfs(wd, &stat); err != nil {
		return 0, 0, err
	}
	total = stat.Blocks * uint64(stat.Bsize)
	avail = stat.Bavail * uint64(stat.Bsize)
	return total, avail, nil
}
