package tool

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/viper"
	"github.com/zaigie/palworld-server-tool/internal/logger"
)

type ConfigEntry struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

func GetConfigFilePath() string {
	cp := viper.GetString("server.config_path")
	if cp != "" {
		return cp
	}
	sp := viper.GetString("save.path")
	if sp == "" {
		return ""
	}
	platform := "Linux"
	candidates := []string{
		filepath.Join(sp, "..", "..", "..", "..", "Saved", "Config", platform+"Server", "PalWorldSettings.ini"),
		filepath.Join(sp, "..", "..", "..", "Saved", "Config", platform+"Server", "PalWorldSettings.ini"),
		filepath.Join(sp, "..", "..", "Saved", "Config", platform+"Server", "PalWorldSettings.ini"),
		filepath.Join(sp, "Saved", "Config", platform+"Server", "PalWorldSettings.ini"),
	}
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	// fallback: assume save.path is directly under Pal/Saved/
	return filepath.Join(sp, "..", "..", "Config", platform+"Server", "PalWorldSettings.ini")
}

func ReadConfig() ([]ConfigEntry, string, error) {
	path := GetConfigFilePath()
	if path == "" {
		return nil, "", fmt.Errorf("server.config_path is not configured")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, "", fmt.Errorf("failed to read config file %s: %w", path, err)
	}
	content := string(data)
	entries, err := parseIniContent(content)
	if err != nil {
		return nil, content, fmt.Errorf("failed to parse config: %w", err)
	}
	return entries, content, nil
}

func WriteConfig(entries []ConfigEntry) error {
	running, err := IsServerRunning()
	if err != nil {
		return fmt.Errorf("failed to check server status: %w", err)
	}
	if running {
		return fmt.Errorf("server is running, please stop it first")
	}
	path := GetConfigFilePath()
	if path == "" {
		return fmt.Errorf("server.config_path is not configured")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("failed to read config file: %w", err)
	}
	content := string(data)
	newContent, err := replaceIniSettings(content, entries)
	if err != nil {
		return fmt.Errorf("failed to update config: %w", err)
	}
	if err := os.WriteFile(path, []byte(newContent), 0644); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}
	logger.Info("PalWorldSettings.ini has been updated\n")
	return nil
}

func parseIniContent(content string) ([]ConfigEntry, error) {
	start := strings.Index(content, "OptionSettings=(")
	if start == -1 {
		return nil, fmt.Errorf("OptionSettings not found in config")
	}
	start += len("OptionSettings=(")
	depth := 1
	var buf strings.Builder
	for i := start; i < len(content); i++ {
		ch := content[i]
		if ch == '(' {
			depth++
		} else if ch == ')' {
			depth--
			if depth == 0 {
				break
			}
		}
		buf.WriteByte(ch)
	}
	body := buf.String()
	var entries []ConfigEntry
	for {
		body = strings.TrimSpace(body)
		if body == "" {
			break
		}
		eqIdx := strings.IndexByte(body, '=')
		if eqIdx == -1 {
			break
		}
		key := strings.TrimSpace(body[:eqIdx])
		rest := body[eqIdx+1:]
		val, next := extractValue(rest)
		entries = append(entries, ConfigEntry{Key: key, Value: val})
		if next == -1 {
			break
		}
		if next < len(rest) && rest[next] == ',' {
			body = rest[next+1:]
		} else {
			body = rest[next:]
		}
	}
	return entries, nil
}

func extractValue(s string) (string, int) {
	s = strings.TrimSpace(s)
	if s == "" {
		return "", -1
	}
	switch s[0] {
	case '"':
		end := strings.IndexByte(s[1:], '"')
		if end == -1 {
			return s[1:], len(s)
		}
		return s[1 : end+1], end + 2
	case '(':
		depth := 1
		for i := 1; i < len(s); i++ {
			switch s[i] {
			case '(':
				depth++
			case ')':
				depth--
				if depth == 0 {
					return s[1:i], i + 1
				}
			}
		}
		return s[1:], len(s)
	default:
		end := strings.IndexAny(s, ",")
		if end == -1 {
			return strings.TrimSpace(s), len(s)
		}
		return strings.TrimSpace(s[:end]), end + 1
	}
}

func replaceIniSettings(content string, entries []ConfigEntry) (string, error) {
	start := strings.Index(content, "OptionSettings=(")
	if start == -1 {
		return "", fmt.Errorf("OptionSettings not found in config")
	}
	prefix := content[:start+len("OptionSettings=(")]
	depth := 1
	end := start + len("OptionSettings=(")
	for i := end; i < len(content); i++ {
		if content[i] == '(' {
			depth++
		} else if content[i] == ')' {
			depth--
			if depth == 0 {
				end = i
				break
			}
		}
	}
	suffix := content[end:]
	existing, err := parseIniContent(content)
	if err != nil {
		return "", err
	}
	entryMap := make(map[string]string, len(existing))
	for _, e := range existing {
		entryMap[e.Key] = e.Value
	}
	for _, e := range entries {
		entryMap[e.Key] = e.Value
	}
	var pairs []string
	for _, e := range existing {
		val := entryMap[e.Key]
		pairs = append(pairs, e.Key+"="+formatValue(val))
	}
	newBody := strings.Join(pairs, ",")
	return prefix + newBody + suffix, nil
}

func formatValue(v string) string {
	if v == "" {
		return "\"\""
	}
	if strings.HasPrefix(v, "\"") && strings.HasSuffix(v, "\"") {
		return v
	}
	if v == "True" || v == "False" || v == "None" {
		return v
	}
	if isNumeric(v) {
		return v
	}
	if strings.Contains(v, ",") || strings.Contains(v, "(") {
		return "(" + v + ")"
	}
	return "\"" + v + "\""
}

func ScanConfigPaths() []string {
	var found []string
	seen := make(map[string]bool)
	sp := viper.GetString("save.path")
	if sp != "" {
		dir := sp
		for i := 0; i < 10; i++ {
			for _, platform := range []string{"Linux", "Windows"} {
				candidate := filepath.Join(dir, "Saved", "Config", platform+"Server", "PalWorldSettings.ini")
				candidate = filepath.Clean(candidate)
				if !seen[candidate] {
					seen[candidate] = true
					if _, err := os.Stat(candidate); err == nil {
						found = append(found, candidate)
					}
				}
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}
	return found
}

func SetConfigPath(path string) error {
	path = filepath.Clean(path)
	if _, err := os.Stat(path); err != nil {
		return fmt.Errorf("config file not found at %s: %w", path, err)
	}
	viper.Set("server.config_path", path)
	logger.Infof("config path set to %s\n", path)
	return nil
}

func isNumeric(s string) bool {
	if s == "" {
		return false
	}
	dot := false
	for i, c := range s {
		if c == '-' && i == 0 {
			continue
		}
		if c == '.' && !dot {
			dot = true
			continue
		}
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}
