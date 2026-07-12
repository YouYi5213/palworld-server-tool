package tool

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/spf13/viper"
	"github.com/zaigie/palworld-server-tool/internal/auth"
	"github.com/zaigie/palworld-server-tool/internal/database"
	"github.com/zaigie/palworld-server-tool/internal/logger"
	"github.com/zaigie/palworld-server-tool/internal/source"
	"github.com/zaigie/palworld-server-tool/internal/system"
	"github.com/zaigie/palworld-server-tool/service"
	"go.etcd.io/bbolt"
)

func ExportSave() (string, error) {
	sourcePath := viper.GetString("save.path")
	levelFilePath, err := getFromSource(sourcePath, "export")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(filepath.Dir(levelFilePath))

	exportDir := filepath.Join(os.TempDir(), "palworld-export")
	os.MkdirAll(exportDir, 0755)
	currentTime := time.Now().Format("2006-01-02-15-04-05")
	zipFile := filepath.Join(exportDir, fmt.Sprintf("save-%s.zip", currentTime))

	if err := system.ZipDir(filepath.Dir(levelFilePath), zipFile); err != nil {
		return "", fmt.Errorf("failed to create export zip: %w", err)
	}
	return zipFile, nil
}

func ImportSave(zipPath string) error {
	savePath := viper.GetString("save.path")
	if savePath == "" {
		return fmt.Errorf("save.path is not configured")
	}
	savDir, err := system.GetSavDir(savePath)
	if err != nil {
		return fmt.Errorf("failed to locate save directory: %w", err)
	}
	tmpDir := filepath.Join(os.TempDir(), "palworld-import-"+uuid.New().String())
	defer os.RemoveAll(tmpDir)

	if err := system.UnzipDir(zipPath, tmpDir); err != nil {
		return fmt.Errorf("failed to unzip save file: %w", err)
	}

	hasLevel := false
	filepath.Walk(tmpDir, func(path string, info os.FileInfo, err error) error {
		if err == nil && info.Name() == "Level.sav" {
			hasLevel = true
		}
		return nil
	})
	if !hasLevel {
		return fmt.Errorf("uploaded archive does not contain Level.sav")
	}

	if _, err := Backup(); err != nil {
		logger.Warnf("failed to backup before import: %v\n", err)
	}

	if err := os.RemoveAll(savDir); err != nil {
		return fmt.Errorf("failed to clear save directory: %w", err)
	}
	os.MkdirAll(savDir, 0755)

	if err := system.CopyDir(tmpDir, savDir); err != nil {
		return fmt.Errorf("failed to copy imported save: %w", err)
	}

	logger.Info("Save imported successfully\n")
	return nil
}

func ResetServerData() error {
	_, err := Backup()
	if err != nil {
		return fmt.Errorf("failed to backup save before reset: %w", err)
	}
	if err := StopServer(); err != nil {
		logger.Warnf("failed to stop server during reset: %v\n", err)
	}
	savePath := viper.GetString("save.path")
	if savePath == "" {
		return fmt.Errorf("save.path is not configured")
	}
	savDir, err := system.GetSavDir(savePath)
	if err != nil {
		return fmt.Errorf("failed to locate save directory: %w", err)
	}
	entries, err := os.ReadDir(savDir)
	if err != nil {
		return fmt.Errorf("failed to read save directory %s: %w", savDir, err)
	}
	for _, entry := range entries {
		fullPath := filepath.Join(savDir, entry.Name())
		if err := os.RemoveAll(fullPath); err != nil {
			return fmt.Errorf("failed to remove %s: %w", fullPath, err)
		}
	}
	logger.Info("Server data has been reset successfully\n")
	return nil
}

type Sturcture struct {
	Players []database.Player `json:"players"`
	Guilds  []database.Guild  `json:"guilds"`
}

func getSavCli() (string, error) {
	savCliPath := viper.GetString("save.decode_path")
	if savCliPath == "" || savCliPath == "/path/to/your/sav_cli" {
		ed, err := system.GetExecDir()
		if err != nil {
			logger.Errorf("error getting exec directory: %s", err)
			return "", err
		}
		savCliPath = filepath.Join(ed, "sav_cli")
		if runtime.GOOS == "windows" {
			savCliPath += ".exe"
		}
	}
	if _, err := os.Stat(savCliPath); err != nil {
		return "", err
	}
	return savCliPath, nil
}

func getPythonScriptPath() (string, error) {
	ed, err := system.GetExecDir()
	if err != nil {
		return "", err
	}
	// Check module/sav_cli.py next to executable
	scriptPath := filepath.Join(ed, "module", "sav_cli.py")
	if _, err := os.Stat(scriptPath); err == nil {
		return scriptPath, nil
	}
	// Check in current working directory
	cwd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	scriptPath = filepath.Join(cwd, "module", "sav_cli.py")
	if _, err := os.Stat(scriptPath); err == nil {
		return scriptPath, nil
	}
	return "", fmt.Errorf("module/sav_cli.py not found")
}

func Decode(file string) error {
	python, err := exec.LookPath("python3")
	if err != nil {
		python, err = exec.LookPath("python")
		if err != nil {
			return errors.New("python not found in PATH")
		}
	}

	scriptPath, err := getPythonScriptPath()
	if err != nil {
		return errors.New("error finding sav_cli.py: " + err.Error())
	}

	levelFilePath, err := getFromSource(file, "decode")
	if err != nil {
		return err
	}
	defer os.RemoveAll(filepath.Dir(levelFilePath))

	baseUrl := fmt.Sprintf("http://127.0.0.1:%d", viper.GetInt("web.port"))
	if viper.GetBool("web.tls") && !strings.HasSuffix(baseUrl, "/") {
		baseUrl = viper.GetString("web.public_url")
	}

	requestUrl := fmt.Sprintf("%s/api/", baseUrl)
	tokenString, err := auth.GenerateToken()
	if err != nil {
		return errors.New("error generating token: " + err.Error())
	}
	execArgs := []string{scriptPath, "-f", levelFilePath, "--request", requestUrl, "--token", tokenString}
	cmd := exec.Command(python, execArgs...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Start()
	if err != nil {
		return errors.New("error starting command: " + err.Error())
	}
	err = cmd.Wait()
	if err != nil {
		return errors.New("error during save parsing: " + err.Error())
	}

	return nil
}

func Backup() (string, error) {
	sourcePath := viper.GetString("save.path")

	levelFilePath, err := getFromSource(sourcePath, "backup")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(filepath.Dir(levelFilePath))

	backupDir, err := GetBackupDir()
	if err != nil {
		return "", fmt.Errorf("failed to get backup directory: %s", err)
	}

	currentTime := time.Now().Format("2006-01-02-15-04-05")
	backupZipFile := filepath.Join(backupDir, fmt.Sprintf("%s.zip", currentTime))
	err = system.ZipDir(filepath.Dir(levelFilePath), backupZipFile)
	if err != nil {
		return "", fmt.Errorf("failed to create backup zip: %s", err)
	}
	return filepath.Base(backupZipFile), nil
}

func GetBackupDir() (string, error) {
	wd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	backDir := filepath.Join(wd, "backups")
	if err = system.CheckAndCreateDir(backDir); err != nil {
		return "", err
	}
	return backDir, nil
}

func CleanOldBackups(db *bbolt.DB, keepDays int) error {
	backupDir, err := GetBackupDir()
	if err != nil {
		return fmt.Errorf("failed to get backup directory: %s", err)
	}

	deadline := time.Now().AddDate(0, 0, -keepDays)

	backups, err := service.ListBackups(db, time.Time{}, time.Now())
	if err != nil {
		return fmt.Errorf("failed to list backups: %s", err)
	}

	for _, backup := range backups {
		if backup.SaveTime.Before(deadline) {
			err = os.Remove(filepath.Join(backupDir, backup.Path))
			if err != nil {
				if !os.IsNotExist(err) {
					logger.Errorf("failed to delete old backup file %s: %s", backup.Path, err)
				}
			}

			err = service.DeleteBackup(db, backup.BackupId)
			if err != nil {
				logger.Errorf("failed to delete backup record from database: %s", err)
			}
		}
	}

	return nil
}

func getFromSource(file, way string) (string, error) {
	var levelFilePath string
	var err error

	if strings.HasPrefix(file, "http://") || strings.HasPrefix(file, "https://") {
		// http(s)://url
		levelFilePath, err = source.DownloadFromHttp(file, way)
		if err != nil {
			return "", errors.New("error downloading file: " + err.Error())
		}
	} else if strings.HasPrefix(file, "k8s://") {
		// k8s://namespace/pod/container:remotePath
		namespace, podName, container, remotePath, err := source.ParseK8sAddress(file)
		if err != nil {
			return "", errors.New("error parsing k8s address: " + err.Error())
		}
		levelFilePath, err = source.CopyFromPod(namespace, podName, container, remotePath, way)
		if err != nil {
			return "", errors.New("error copying file from pod: " + err.Error())
		}
	} else if strings.HasPrefix(file, "docker://") {
		// docker://containerID(Name):remotePath
		containerId, remotePath, err := source.ParseDockerAddress(file)
		if err != nil {
			return "", errors.New("error parsing docker address: " + err.Error())
		}
		levelFilePath, err = source.CopyFromContainer(containerId, remotePath, way)
		if err != nil {
			return "", errors.New("error copying file from container: " + err.Error())
		}
	} else {
		// local file
		levelFilePath, err = source.CopyFromLocal(file, way)
		if err != nil {
			return "", errors.New("error copying file to temporary directory: " + err.Error())
		}
	}
	return levelFilePath, nil
}
