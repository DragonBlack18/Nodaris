from pathlib import Path


BRANDING_FILES = (
    "nodaris_icon.ico",
    "nodaris_icon.png",
    "nodaris_icon_256.png",
    "nodaris_logo_reference.jpg",
)


def verify_build(project_root: Path) -> list[str]:
    dist = Path(project_root) / "dist"
    errors = []

    required_files = [
        dist / "NODARIS Core" / "NODARIS Core.exe",
        dist / "NODARIS Core" / "_internal" / "ips.json",
        dist / "NODARIS Admin" / "NODARIS Admin.exe",
        dist
        / "NODARIS Admin"
        / "_internal"
        / "PySide6"
        / "plugins"
        / "platforms"
        / "qwindows.dll",
        dist / "NODARIS TV" / "NODARIS TV.exe",
        dist
        / "NODARIS TV"
        / "_internal"
        / "PySide6"
        / "plugins"
        / "platforms"
        / "qwindows.dll",
    ]

    for app_name in ("NODARIS Admin", "NODARIS TV"):
        branding_dir = dist / app_name / "_internal" / "assets" / "branding"
        required_files.extend(
            branding_dir / filename
            for filename in BRANDING_FILES
        )

    for file_path in required_files:
        if not file_path.is_file():
            errors.append(f"Arquivo ausente: {file_path}")
        elif file_path.stat().st_size <= 0:
            errors.append(f"Arquivo vazio: {file_path}")

    return errors


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    errors = verify_build(project_root)

    if errors:
        print("NODARIS build verification: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("NODARIS build verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
