import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fake_client import FIRST_WAV, SECOND_WAV, ZERO_WAV, run_fixture_call


def print_event(event: dict) -> None:
    event_name = event.get("event")
    if event_name == "clear":
        print("agent audio cleared because of barge-in")
    else:
        print(event)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local fake WAV call demo.")
    parser.add_argument("--barge-in-delay-ms", type=int, default=300)
    args = parser.parse_args()

    asyncio.run(
        run_fixture_call(
            zero_wav=ZERO_WAV,
            first_wav=FIRST_WAV,
            second_wav=SECOND_WAV,
            barge_in_delay_ms=args.barge_in_delay_ms,
            on_event=print_event,
        )
    )


if __name__ == "__main__":
    main()
