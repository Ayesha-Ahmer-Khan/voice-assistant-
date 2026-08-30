import keyboard
from recorder import record_audio_until_release
from transcriber import transcribe
from config import HOTKEY
from command_parser import parse_command
from actuator_controller import execute_command


def main():
    print(f"Hold {HOTKEY} to talk.")

    while True:
        keyboard.wait(HOTKEY)

        audio = record_audio_until_release()

        if audio:
            user_text = transcribe(audio)

            print()
            print(repr(user_text))
            print()

            command = parse_command(user_text)

            print("Parsed command:", command)

            execute_command(command)


if __name__ == "__main__":
    main()