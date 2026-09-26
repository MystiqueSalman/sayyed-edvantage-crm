
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "Sayyed_EdVantage_Master_KB_BATCH25.py"

OLD = '"Certification details are not verified in the current Master KB."'

NEW = (
    '"Certification details are not verified in the current Master KB. " '
    '"I do not want to invent certification details that have not been " '
    '"officially verified."'
)

def main():
    if not TARGET.exists():
        raise FileNotFoundError(
            f"Could not find {TARGET.name} in {TARGET.parent}"
        )

    text = TARGET.read_text(encoding="utf-8")

    if "I do not want to invent certification details" in text:
        print("Batch 25 certification safety wording is already patched.")
        return

    if OLD not in text:
        raise RuntimeError(
            "Expected Batch-25 certification wording was not found. "
            "No file was changed."
        )

    updated = text.replace(OLD, NEW, 1)
    TARGET.write_text(updated, encoding="utf-8")

    print("PATCH APPLIED: Batch 25 certification safety wording.")
    print(f"Updated: {TARGET}")

if __name__ == "__main__":
    main()
