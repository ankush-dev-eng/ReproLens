"""Git repository cloning, revision resolution, and isolated worktrees."""

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from reprolens.config import Config


def _run_git(args: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    """Run git command with terminal prompts and hooks disabled."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    # Use empty temp dir for hooks to prevent any arbitrary repo hooks from executing
    empty_hooks = Path(tempfile.gettempdir()) / "reprolens_empty_hooks"
    empty_hooks.mkdir(exist_ok=True)

    cmd = ["git", "-c", f"core.hooksPath={empty_hooks}"] + args
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\nStderr: {res.stderr}")
    return res.stdout.strip()


def slugify_repo_url(repo_url: str) -> str:
    """Derive clean directory name from repository URL or owner/repo."""
    clean = re.sub(r"^(?:https?://github\.com/)", "", repo_url).strip("/")
    clean = re.sub(r"\.git$", "", clean)
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", clean)


class RepositoryManager:
    """Manages repository caches, revision checkout, and worktrees."""

    def __init__(self, cache_base_dir: Path | None = None) -> None:
        self.cache_base_dir = cache_base_dir or (Config.PROJECT_ROOT / ".cache_repos")
        self.cache_base_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_cache_dir(self, repo_url: str) -> Path:
        slug = slugify_repo_url(repo_url)
        return self.cache_base_dir / slug

    def clone_or_fetch(self, repo_url: str) -> Path:
        """Clone repository or fetch latest updates safely."""
        repo_dir = self.get_repo_cache_dir(repo_url)
        # Normalize clone URL
        if not repo_url.startswith("http") and not repo_url.startswith("git@"):
            clone_target = f"https://github.com/{repo_url.strip('/')}.git"
        else:
            clone_target = repo_url

        if repo_dir.exists() and (repo_dir / ".git").exists():
            # Existing cache: fetch all branches and tags
            try:
                _run_git(["fetch", "--all", "--tags", "-q"], cwd=repo_dir)
                return repo_dir
            except Exception:
                # If existing cache is corrupted, re-clone
                shutil.rmtree(repo_dir, ignore_errors=True)

        _run_git(
            [
                "clone",
                "--no-recurse-submodules",
                clone_target,
                str(repo_dir.resolve()),
            ]
        )
        return repo_dir

    def resolve_revision(
        self,
        repo_dir: Path,
        explicit_commit: str | None = None,
        issue_created_at: str | None = None,
    ) -> str:
        """Select revision SHA based on explicit commit or issue creation timestamp."""
        if explicit_commit and explicit_commit.strip():
            return _run_git(["rev-parse", explicit_commit.strip()], cwd=repo_dir)

        if issue_created_at:
            # Query commit immediately preceding issue creation
            try:
                sha = _run_git(
                    ["rev-list", "-1", f"--before={issue_created_at}", "HEAD"],
                    cwd=repo_dir,
                )
                if sha:
                    return sha
            except Exception:
                pass

        # Fallback to HEAD
        return _run_git(["rev-parse", "HEAD"], cwd=repo_dir)

    def checkout_worktree(self, repo_dir: Path, commit_sha: str) -> Path:
        """Create an isolated worktree at commit_sha."""
        worktree_dir = Path(tempfile.mkdtemp(prefix="reprolens_wt_"))
        # Detach worktree at target SHA
        _run_git(
            ["worktree", "add", "--detach", str(worktree_dir.resolve()), commit_sha],
            cwd=repo_dir,
        )
        return worktree_dir

    def cleanup_worktree(self, repo_dir: Path, worktree_dir: Path) -> None:
        """Remove a temporary worktree."""
        with contextlib.suppress(Exception):
            _run_git(
                ["worktree", "remove", "--force", str(worktree_dir.resolve())],
                cwd=repo_dir,
            )
        shutil.rmtree(worktree_dir, ignore_errors=True)
