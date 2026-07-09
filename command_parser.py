import re


def parse_command(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)

    print("Cleaned text:", text)

    command = {
        "actuators": [],
        "duration": None,
        "direction": None
    }

    # Direction
    if "up" in text:
        command["direction"] = "up"
    elif "down" in text:
        command["direction"] = "down"

    tokens = text.split()
    actuator_tokens = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.isdigit():
            # Check if this number is duration
            if i + 1 < len(tokens):
                next_token = tokens[i + 1]
                if next_token in ["sec", "second", "seconds"]:
                    command["duration"] = int(token)
                    break

            # Otherwise it's an actuator
            actuator_tokens.append(int(token))

        i += 1

    command["actuators"] = actuator_tokens

    return command