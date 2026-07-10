package tool

import (
	"fmt"
	"os/exec"
	"runtime"
	"strings"

	"github.com/spf13/viper"
)

func StartServer() error {
	cmdStr := viper.GetString("server.start_command")
	if cmdStr == "" {
		return fmt.Errorf("server.start_command is not configured")
	}
	cmd := exec.Command("sh", "-c", cmdStr)
	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/c", cmdStr)
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start server: %w", err)
	}
	return nil
}

func StopServer() error {
	cmdStr := viper.GetString("server.stop_command")
	if cmdStr != "" {
		cmd := exec.Command("sh", "-c", cmdStr)
		if runtime.GOOS == "windows" {
			cmd = exec.Command("cmd", "/c", cmdStr)
		}
		out, err := cmd.CombinedOutput()
		if err != nil {
			return fmt.Errorf("stop command failed: %w, output: %s", err, string(out))
		}
		return nil
	}
	pattern := viper.GetString("server.stop_pattern")
	if pattern == "" {
		pattern = "PalServer"
	}
	var stopCmd *exec.Cmd
	if runtime.GOOS == "windows" {
		stopCmd = exec.Command("taskkill", "/F", "/IM", pattern)
	} else {
		stopCmd = exec.Command("pkill", "-f", pattern)
	}
	out, err := stopCmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to stop server with pattern %q: %w, output: %s", pattern, err, string(out))
	}
	return nil
}

func IsServerRunning() (bool, error) {
	pattern := viper.GetString("server.stop_pattern")
	if pattern == "" {
		pattern = "PalServer"
	}
	var checkCmd *exec.Cmd
	if runtime.GOOS == "windows" {
		checkCmd = exec.Command("tasklist", "/FI", fmt.Sprintf("IMAGENAME eq %s*", pattern), "/NH")
	} else {
		checkCmd = exec.Command("pgrep", "-f", pattern)
	}
	out, err := checkCmd.CombinedOutput()
	if err != nil {
		if runtime.GOOS == "windows" {
			if strings.Contains(string(out), "No tasks") || strings.Contains(string(out), "INFO:") {
				return false, nil
			}
			return false, nil
		}
		if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 1 {
			return false, nil
		}
		return false, fmt.Errorf("failed to check server status: %w", err)
	}
	if runtime.GOOS == "windows" {
		return !strings.Contains(string(out), "No tasks"), nil
	}
	return strings.TrimSpace(string(out)) != "", nil
}
