"""Entry point: `gusteau` or `python -m gusteau`."""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "gusteau.api:create_app",
        factory=True,
        host=os.environ.get("GUSTEAU_HOST", "0.0.0.0"),
        port=int(os.environ.get("GUSTEAU_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
