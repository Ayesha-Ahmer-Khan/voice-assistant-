def execute_command(command):
    direction = command["direction"]
    actuators = command["actuators"]
    duration = command["duration"]

    if direction == "all stop":
        print("Stopping all actuators.")
        return

    if direction == "all move":
        print("Moving all actuators.")
        return

    if not actuators:
        print("No actuators specified.")
        return

    if direction not in ["up", "down"]:
        print("Invalid direction.")
        return

    if duration is None:
        print("No duration specified.")
        return

    print(
        f"Moving actuators {actuators} "
        f"{direction} for {duration} sec"
    )