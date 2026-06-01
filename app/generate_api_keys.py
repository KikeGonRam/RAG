"""
Generador simple de API keys para colaboradores.
Uso:
  python -m app.generate_api_keys --count 5
"""

import argparse
import secrets


def build_key(prefix: str) -> str:
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generar API keys seguras")
    parser.add_argument("--count", type=int, default=1, help="Numero de keys a generar")
    parser.add_argument(
        "--prefix",
        type=str,
        default="colab_",
        help="Prefijo opcional para identificar tus keys",
    )
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count debe ser mayor o igual a 1")

    keys = [build_key(args.prefix) for _ in range(args.count)]

    print("# Keys individuales")
    for key in keys:
        print(key)

    print("\n# Valor para API_KEYS en .env")
    print(",".join(keys))


if __name__ == "__main__":
    main()
