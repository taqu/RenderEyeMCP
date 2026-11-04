package captures

import (
	"os"
	"path/filepath"
	"strings"
)

// isRDC reports whether path has a .rdc extension (case-insensitive).
func isRDC(path string) bool {
	return strings.EqualFold(filepath.Ext(path), ".rdc")
}

// canonicalPath returns an absolute path with symlinks (and, on Windows,
// 8.3 short names) resolved.  For a path that no longer exists — e.g. a file
// reported deleted by the watcher — the parent directory is resolved and the
// base name re-attached, so the result still matches the stored record.
func canonicalPath(path string) string {
	abs, err := filepath.Abs(path)
	if err != nil {
		abs = path
	}
	if resolved, err := filepath.EvalSymlinks(abs); err == nil {
		return resolved
	}
	if dir, err := filepath.EvalSymlinks(filepath.Dir(abs)); err == nil {
		return filepath.Join(dir, filepath.Base(abs))
	}
	return filepath.Clean(abs)
}

// scanDirectory returns canonical paths of .rdc files at least minSize bytes
// large.  Inaccessible entries are skipped; symlinked directory cycles are
// broken by tracking resolved directories; results are de-duplicated.
func scanDirectory(dir string, recursive bool, minSize int64) []string {
	info, err := os.Stat(dir)
	if err != nil || !info.IsDir() {
		return nil
	}
	seenDirs := map[string]bool{canonicalPath(dir): true}
	seenFiles := map[string]bool{}
	var out []string

	var walk func(d string)
	walk = func(d string) {
		entries, err := os.ReadDir(d)
		if err != nil {
			return
		}
		for _, e := range entries {
			full := filepath.Join(d, e.Name())
			st, err := os.Stat(full) // follows symlinks
			if err != nil {
				continue
			}
			if st.IsDir() {
				if !recursive {
					continue
				}
				resolved := canonicalPath(full)
				if seenDirs[resolved] {
					continue
				}
				seenDirs[resolved] = true
				walk(full)
				continue
			}
			if !st.Mode().IsRegular() || !isRDC(full) || st.Size() < minSize {
				continue
			}
			resolved := canonicalPath(full)
			if seenFiles[resolved] {
				continue
			}
			seenFiles[resolved] = true
			out = append(out, resolved)
		}
	}
	walk(dir)
	return out
}
