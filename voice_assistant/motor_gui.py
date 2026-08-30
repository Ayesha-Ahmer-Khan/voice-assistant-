import tkinter as tk
import json
import os
import serial
import time
import threading

from tkinter import ttk

# ============================================================
# VOICE ASSISTANT BACKEND
# ============================================================

from recorder import record_audio_until_release
from transcriber import transcribe
from command_parser import parse_command
from config import HOTKEY


# ============================================================
# CONFIGURATION
# ============================================================

NUM_MOTORS = 120
SERIAL_PORT = "COM3"
BAUD_RATE = 9600

JSON_FILE = "motor_times.json"

SERIAL_RECONNECT_MS = 2000
VISUAL_UPDATE_MS = 200

# ============================================================
# SERIAL CONNECTION
# ============================================================

ser = None


def connect_serial():
    global ser

    try:
        if ser is not None and ser.is_open:
            return True

        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=1
        )

        print("Serial port connected:", SERIAL_PORT)

        # Give Arduino time after serial opening/reset
        time.sleep(2)

        return True

    except Exception as e:
        print("Serial connection failed:", e)
        ser = None
        return False


connect_serial()


# ============================================================
# MOTOR COMMAND OBJECT
# ============================================================

class MotorCommand:

    def __init__(
        self,
        command_id,
        direction,
        motors,
        duration
    ):

        self.command_id = command_id
        self.direction = direction.upper()
        self.motors = motors
        self.duration = int(duration)

    def to_serial(self):

        motor_list = ",".join(
            str(motor)
            for motor in self.motors
        )

        return (
            f"CMD:"
            f"{self.command_id}:"
            f"{self.direction}:"
            f"{self.duration}:"
            f"{motor_list}\n"
        )


# ============================================================
# GUI
# ============================================================

class MotorControlGUI:

    def __init__(self, root, num_motors=NUM_MOTORS):

        self.root = root

        self.root.title(
            "Motor Control GUI - 120 Motors"
        )

        self.root.geometry(
            "1400x800"
        )

        self.num_motors = num_motors

        # ----------------------------------------------------
        # MOTOR IDs
        # ----------------------------------------------------

        self.motor_ids = [
            f"{i:02d}"
            for i in range(num_motors)
        ]

        # ----------------------------------------------------
        # MOTOR TIMINGS
        # ----------------------------------------------------

        self.clockwise_vars = [
            tk.IntVar(value=1000)
            for _ in range(num_motors)
        ]

        self.counterclockwise_vars = [
            tk.IntVar(value=1000)
            for _ in range(num_motors)
        ]

        # ----------------------------------------------------
        # MOTOR SELECTION
        # ----------------------------------------------------

        self.selected_motors = [
            tk.BooleanVar(value=False)
            for _ in range(num_motors)
        ]

        self.group_duration_var = tk.IntVar(
            value=3
        )

        # ----------------------------------------------------
        # MOTOR VISUAL STATES
        # ----------------------------------------------------

        self.motor_states = [
            "stopped"
            for _ in range(num_motors)
        ]

        self.motor_end_times = [
            0
            for _ in range(num_motors)
        ]

        # ----------------------------------------------------
        # GUI REFERENCES
        # ----------------------------------------------------

        self.motor_controls = []

        self.checkbox_refs = [
            None
            for _ in range(num_motors)
        ]

        # ----------------------------------------------------
        # COMMAND SYSTEM
        # ----------------------------------------------------

        self.command_counter = 0

        self.last_visual_update = 0

        # ----------------------------------------------------
        # VOICE SYSTEM
        # ----------------------------------------------------

        self.voice_running = False
        self.voice_thread = None
        self.voice_hotkey_hook = None

        # ----------------------------------------------------
        # STATUS LABELS
        # ----------------------------------------------------

        self.sd_status_label = None
        self.timings_status_label = None
        self.connection_status = None
        self.voice_status = None
        self.voice_text_label = None
        self.command_status_label = None

        # ----------------------------------------------------
        # TKINTER
        # ----------------------------------------------------

        root.option_add(
            "*tearOff",
            False
        )

        # ====================================================
        # TOP CONTROL FRAME
        # ====================================================

        control_frame = tk.Frame(
            root,
            bg="lightgray",
            padx=10,
            pady=10
        )

        control_frame.pack(
            fill="x"
        )

        # ----------------------------------------------------
        # HALT
        # ----------------------------------------------------

        halt_button = tk.Button(
            control_frame,
            text="HALT ALL",
            command=self.halt_action,
            bg="red",
            fg="white",
            font=("Arial", 10, "bold")
        )

        halt_button.grid(
            row=0,
            column=0,
            padx=5,
            pady=5
        )

        # ----------------------------------------------------
        # ALL UP
        # ----------------------------------------------------

        all_up_button = tk.Button(
            control_frame,
            text="ALL UP",
            command=self.all_motors_up,
            bg="lightgreen",
            font=("Arial", 9)
        )

        all_up_button.grid(
            row=0,
            column=1,
            padx=2
        )

        # ----------------------------------------------------
        # ALL DOWN
        # ----------------------------------------------------

        all_down_button = tk.Button(
            control_frame,
            text="ALL DOWN",
            command=self.all_motors_down,
            bg="lightcoral",
            font=("Arial", 9)
        )

        all_down_button.grid(
            row=0,
            column=2,
            padx=2
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        save_button = tk.Button(
            control_frame,
            text="Save Times",
            command=self.save_times_to_file,
            bg="blue",
            fg="white",
            font=("Arial", 9)
        )

        save_button.grid(
            row=0,
            column=3,
            padx=5
        )

        # ----------------------------------------------------
        # SEND TIMINGS
        # ----------------------------------------------------

        send_button = tk.Button(
            control_frame,
            text="Send All Timings",
            command=self.send_timings_to_arduino,
            bg="green",
            fg="white",
            font=("Arial", 9)
        )

        send_button.grid(
            row=0,
            column=4,
            padx=5
        )

        # ====================================================
        # GROUP CONTROL
        # ====================================================

        group_frame = tk.Frame(
            control_frame,
            bg="lightgray"
        )

        group_frame.grid(
            row=1,
            column=0,
            columnspan=7,
            pady=10,
            sticky="w"
        )

        tk.Label(
            group_frame,
            text="Group Control:",
            bg="lightgray",
            font=("Arial", 9, "bold")
        ).grid(
            row=0,
            column=0,
            padx=5
        )

        tk.Label(
            group_frame,
            text="Duration:",
            bg="lightgray"
        ).grid(
            row=0,
            column=1
        )

        duration_spin = tk.Spinbox(
            group_frame,
            from_=1,
            to=3600,
            width=5,
            textvariable=self.group_duration_var
        )

        duration_spin.grid(
            row=0,
            column=2,
            padx=3
        )

        tk.Label(
            group_frame,
            text="sec",
            bg="lightgray"
        ).grid(
            row=0,
            column=3
        )

        tk.Button(
            group_frame,
            text="Selected UP",
            command=self.selected_up,
            bg="lightgreen"
        ).grid(
            row=0,
            column=4,
            padx=3
        )

        tk.Button(
            group_frame,
            text="Selected DOWN",
            command=self.selected_down,
            bg="lightcoral"
        ).grid(
            row=0,
            column=5,
            padx=3
        )

        tk.Button(
            group_frame,
            text="Select All",
            command=self.select_all
        ).grid(
            row=0,
            column=6,
            padx=3
        )

        tk.Button(
            group_frame,
            text="Clear All",
            command=self.clear_all
        ).grid(
            row=0,
            column=7,
            padx=3
        )

        # ====================================================
        # STATUS FRAME
        # ====================================================

        status_frame = tk.Frame(
            control_frame,
            bg="lightgray"
        )

        status_frame.grid(
            row=2,
            column=0,
            columnspan=8,
            sticky="w"
        )

        self.sd_status_label = tk.Label(
            status_frame,
            text="SD: N/A",
            bg="lightgray"
        )

        self.sd_status_label.pack(
            side="left",
            padx=5
        )

        self.timings_status_label = tk.Label(
            status_frame,
            text="Timings: LOADING",
            bg="lightgray"
        )

        self.timings_status_label.pack(
            side="left",
            padx=5
        )

        self.connection_status = tk.Label(
            status_frame,
            text="Arduino: DISCONNECTED",
            bg="lightgray",
            fg="red"
        )

        self.connection_status.pack(
            side="left",
            padx=20
        )

        # ====================================================
        # VOICE STATUS
        # ====================================================

        voice_frame = tk.Frame(
            control_frame,
            bg="lightgray"
        )

        voice_frame.grid(
            row=3,
            column=0,
            columnspan=8,
            sticky="w",
            pady=3
        )

        self.voice_status = tk.Label(
            voice_frame,
            text="Voice: READY - Hold SPACE",
            bg="lightgray",
            fg="green",
            font=("Arial", 9, "bold")
        )

        self.voice_status.pack(
            side="left",
            padx=5
        )

        self.voice_text_label = tk.Label(
            voice_frame,
            text="Heard: ---",
            bg="lightgray"
        )

        self.voice_text_label.pack(
            side="left",
            padx=20
        )

        # ====================================================
        # COMMAND STATUS
        # ====================================================

        self.command_status_label = tk.Label(
            control_frame,
            text="Command: ---",
            bg="lightgray",
            anchor="w"
        )

        self.command_status_label.grid(
            row=4,
            column=0,
            columnspan=8,
            sticky="w",
            padx=5
        )

        # ====================================================
        # SCROLLABLE MOTOR AREA
        # ====================================================

        self.canvas = tk.Canvas(
            root,
            bg="white",
            highlightthickness=0
        )

        self.scrollbar = tk.Scrollbar(
            root,
            orient="vertical",
            command=self.canvas.yview
        )

        self.scrollable_frame = tk.Frame(
            self.canvas,
            bg="white"
        )

        self.scrollable_frame.bind(
            "<Configure>",
            lambda event:
                self.canvas.configure(
                    scrollregion=
                    self.canvas.bbox("all")
                )
        )

        self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )

        self.canvas.configure(
            yscrollcommand=self.scrollbar.set
        )

        self.canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.scrollbar.pack(
            side="right",
            fill="y"
        )

        self.canvas.bind_all(
            "<MouseWheel>",
            self.on_mouse_wheel
        )

        # ====================================================
        # CREATE 120 MOTOR PANELS
        # ====================================================

        for i in range(num_motors):
            self.create_motor_control(i)

        # ====================================================
        # STARTUP TASKS
        # ====================================================

        self.root.after(
            100,
            self.load_times_from_file
        )

        self.root.after(
            100,
            self.update_layout
        )

        self.root.after(
            100,
            self.update_visual_states
        )

        self.root.after(
            500,
            self.register_voice_hotkey
        )

        self.root.after(
            1000,
            self.check_serial_status
        )

        self.root.bind(
            "<Configure>",
            self.on_resize
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    # ============================================================
    # SERIAL
    # ============================================================

    def send_serial(self, command):

        global ser

        print(
            "Sending:",
            command.strip()
        )

        try:

            if ser is None or not ser.is_open:

                if not connect_serial():
                    return False

            ser.write(
                command.encode("ascii")
            )

            ser.flush()

            return True

        except Exception as e:

            print(
                "Serial send error:",
                e
            )

            try:
                ser.close()
            except Exception:
                pass

            ser = None

            return False

    # ============================================================
    # STANDARD MOTOR COMMAND
    # ============================================================

    def send_motor_command(
        self,
        direction,
        motors,
        duration
    ):

        if not motors:

            print(
                "No motors specified."
            )

            return False

        direction = direction.upper()

        if direction not in [
            "UP",
            "DOWN"
        ]:

            print(
                "Invalid direction:",
                direction
            )

            return False

        try:

            duration = int(duration)

        except Exception:

            print(
                "Invalid duration."
            )

            return False

        if duration <= 0:

            print(
                "Duration must be greater than zero."
            )

            return False

        # Remove duplicates
        motors = list(
            dict.fromkeys(
                int(m) for m in motors
            )
        )

        # Validate motors
        for motor in motors:

            if motor < 0 or motor >= self.num_motors:

                print(
                    "Invalid motor:",
                    motor
                )

                return False

        # ----------------------------------------------------
        # Generate command ID
        # ----------------------------------------------------

        self.command_counter += 1

        command = MotorCommand(
            self.command_counter,
            direction,
            motors,
            duration
        )

        serial_command = (
            command.to_serial()
        )

        print()
        print(
            "=============================="
        )
        print(
            "MOTOR COMMAND"
        )
        print(
            "=============================="
        )
        print(
            "ID:",
            command.command_id
        )
        print(
            "Direction:",
            command.direction
        )
        print(
            "Motors:",
            command.motors
        )
        print(
            "Duration:",
            command.duration,
            "seconds"
        )
        print(
            "Serial:",
            serial_command.strip()
        )

        success = self.send_serial(
            serial_command
        )

        if success:

            current_time = (
                time.time() * 1000
            )

            for motor in motors:

                if direction == "UP":

                    self.motor_states[motor] = (
                        "moving_up"
                    )

                else:

                    self.motor_states[motor] = (
                        "moving_down"
                    )

                self.motor_end_times[motor] = (
                    current_time +
                    duration * 1000
                )

            self.command_status_label.config(
                text=
                f"Command {command.command_id} "
                f"sent: {direction} "
                f"{motors} "
                f"for {duration}s"
            )

        return success

    # ============================================================
    # VOICE
    # ============================================================

    def register_voice_hotkey(self):

        try:

            import keyboard

            self.voice_hotkey_hook = (
                keyboard.on_press_key(
                    HOTKEY,
                    self.on_voice_hotkey
                )
            )

            print(
                "Voice hotkey enabled: hold",
                HOTKEY,
                "to speak."
            )

        except Exception as e:

            print(
                "Voice hotkey error:",
                e
            )

            self.voice_status.config(
                text="Voice: HOTKEY ERROR",
                fg="red"
            )

    def on_voice_hotkey(self, event):

        if not self.voice_running:

            self.start_voice_command()

    def start_voice_command(self):

        if self.voice_running:
            return

        self.voice_running = True

        self.voice_status.config(
            text="Voice: RECORDING",
            fg="red"
        )

        self.voice_text_label.config(
            text="Heard: Listening..."
        )

        self.voice_thread = threading.Thread(
            target=self.voice_worker,
            daemon=True
        )

        self.voice_thread.start()

    def voice_worker(self):

        try:

            audio = (
                record_audio_until_release()
            )

            if not audio:

                self.root.after(
                    0,
                    lambda:
                    self.voice_finished(
                        "No audio recorded."
                    )
                )

                return

            self.root.after(
                0,
                lambda:
                self.voice_status.config(
                    text="Voice: TRANSCRIBING",
                    fg="orange"
                )
            )

            user_text = transcribe(
                audio
            )

            print(
                "Voice text:",
                user_text
            )

            command = parse_command(
                user_text
            )

            print(
                "Parsed command:",
                command
            )

            self.root.after(
                0,
                lambda text=user_text,
                cmd=command:
                self.execute_voice_command(
                    text,
                    cmd
                )
            )

        except Exception as e:

            print(
                "Voice error:",
                e
            )

            self.root.after(
                0,
                lambda error=str(e):
                self.voice_finished(
                    "Voice error: " + error
                )
            )

    def execute_voice_command(
        self,
        user_text,
        command
    ):

        self.voice_text_label.config(
            text=f"Heard: {user_text}"
        )

        print()
        print(
            "========================================"
        )
        print(
            "VOICE COMMAND"
        )
        print(
            "========================================"
        )

        print(
            "Heard:",
            user_text
        )

        print(
            "Parsed:",
            command
        )

        actuators = command.get(
            "actuators",
            []
        )

        duration = command.get(
            "duration"
        )

        direction = command.get(
            "direction"
        )

        # ----------------------------------------------------
        # Direction
        # ----------------------------------------------------

        if direction is None:

            self.voice_finished(
                "No direction specified."
            )

            return

        direction = direction.lower()

        # ----------------------------------------------------
        # Emergency stop
        # ----------------------------------------------------

        if direction == "all stop":

            self.halt_action()

            self.voice_finished(
                "All motors stopped."
            )

            return

        # ----------------------------------------------------
        # All motors UP
        # ----------------------------------------------------

        if direction == "all move":

            if duration is None:
                duration = 1

            success = self.send_motor_command(
                "UP",
                list(range(self.num_motors)),
                duration
            )

            if success:

                self.voice_finished(
                    "All motors moving UP."
                )

            else:

                self.voice_finished(
                    "Failed to send command."
                )

            return

        # ----------------------------------------------------
        # Validate motors
        # ----------------------------------------------------

        if not actuators:

            self.voice_finished(
                "No motors specified."
            )

            return

        # ----------------------------------------------------
        # Validate duration
        # ----------------------------------------------------

        if duration is None:

            self.voice_finished(
                "No duration specified."
            )

            return

        # ----------------------------------------------------
        # Validate direction
        # ----------------------------------------------------

        if direction not in [
            "up",
            "down"
        ]:

            self.voice_finished(
                "Invalid direction."
            )

            return

        # ----------------------------------------------------
        # Validate motor numbers
        # ----------------------------------------------------

        motors = []

        for motor in actuators:

            try:

                motor = int(motor)

            except Exception:

                self.voice_finished(
                    f"Invalid motor ID: {motor}"
                )

                return

            if not (
                0 <= motor < self.num_motors
            ):

                self.voice_finished(
                    f"Invalid motor ID: {motor}. "
                    f"Valid IDs: "
                    f"0-{self.num_motors - 1}"
                )

                return

            motors.append(
                motor
            )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        success = self.send_motor_command(
            direction.upper(),
            motors,
            duration
        )

        if success:

            result = (
                f"Executed: "
                f"{direction.upper()} "
                f"{motors} "
                f"for {duration}s"
            )

            self.voice_finished(
                result
            )

        else:

            self.voice_finished(
                "Failed to send command to Arduino."
            )

    def voice_finished(self, message):

        print(
            "Voice result:",
            message
        )

        self.voice_running = False

        self.voice_status.config(
            text="Voice: READY - Hold SPACE",
            fg="green"
        )

        self.voice_text_label.config(
            text=f"Voice result: {message}"
        )

    # ============================================================
    # INDIVIDUAL MOTOR COMMANDS
    # ============================================================

    def send_individual_up(
        self,
        motor_index
    ):

        motor_id = int(
            self.motor_ids[motor_index]
        )

        self.send_motor_command(
            "UP",
            [motor_id],
            1
        )

    def send_individual_down(
        self,
        motor_index
    ):

        motor_id = int(
            self.motor_ids[motor_index]
        )

        self.send_motor_command(
            "DOWN",
            [motor_id],
            1
        )

    def send_quick_up(
        self,
        motor_index
    ):

        self.send_individual_up(
            motor_index
        )

    def send_quick_down(
        self,
        motor_index
    ):

        self.send_individual_down(
            motor_index
        )

    # ============================================================
    # GROUP COMMANDS
    # ============================================================

    def selected_up(self):

        selected = (
            self.get_selected_motor_ids()
        )

        motors = [
            int(x)
            for x in selected
        ]

        duration = (
            self.group_duration_var.get()
        )

        self.send_motor_command(
            "UP",
            motors,
            duration
        )

    def selected_down(self):

        selected = (
            self.get_selected_motor_ids()
        )

        motors = [
            int(x)
            for x in selected
        ]

        duration = (
            self.group_duration_var.get()
        )

        self.send_motor_command(
            "DOWN",
            motors,
            duration
        )

    def get_selected_motor_ids(self):

        return [
            self.motor_ids[i]
            for i in range(self.num_motors)
            if self.selected_motors[i].get()
        ]

    # ============================================================
    # ALL MOTORS
    # ============================================================

    def all_motors_up(self):

        duration = (
            self.group_duration_var.get()
        )

        self.send_motor_command(
            "UP",
            list(range(self.num_motors)),
            duration
        )

    def all_motors_down(self):

        duration = (
            self.group_duration_var.get()
        )

        self.send_motor_command(
            "DOWN",
            list(range(self.num_motors)),
            duration
        )

    # ============================================================
    # HALT
    # ============================================================

    def halt_action(self):

        global ser

        if ser is None or not ser.is_open:

            print(
                "Arduino not connected."
            )

            return

        self.command_counter += 1

        command = (
            f"CMD:"
            f"{self.command_counter}:"
            f"STOP:"
            f"0:"
            f"ALL\n"
        )

        if self.send_serial(command):

            for i in range(
                self.num_motors
            ):

                self.motor_states[i] = (
                    "stopped"
                )

                self.motor_end_times[i] = 0

            self.command_status_label.config(
                text=
                f"Command {self.command_counter}: "
                f"EMERGENCY STOP sent"
            )

    # ============================================================
    # SELECTION
    # ============================================================

    def select_all(self):

        for i in range(
            self.num_motors
        ):

            self.selected_motors[i].set(
                True
            )

            self.update_checkbox_color(
                i
            )

    def clear_all(self):

        for i in range(
            self.num_motors
        ):

            self.selected_motors[i].set(
                False
            )

            self.update_checkbox_color(
                i
            )

    def toggle_motor_selection(
        self,
        motor_index
    ):

        current = (
            self.selected_motors[
                motor_index
            ].get()
        )

        self.selected_motors[
            motor_index
        ].set(
            not current
        )

        self.update_checkbox_color(
            motor_index
        )

    def update_checkbox_color(
        self,
        motor_index
    ):

        if motor_index >= len(
            self.motor_controls
        ):

            return

        frame = (
            self.motor_controls[
                motor_index
            ]
        )

        checkbox = (
            self.checkbox_refs[
                motor_index
            ]
        )

        if self.selected_motors[
            motor_index
        ].get():

            frame.config(
                bg="#FFCCCC"
            )

            checkbox.config(
                bg="#FF9999",
                selectcolor="#FF6666"
            )

        else:

            frame.config(
                bg="SystemButtonFace"
            )

            checkbox.config(
                bg="white",
                selectcolor="lightblue"
            )

    # ============================================================
    # MOTOR PANEL
    # ============================================================

    def create_motor_control(
        self,
        motor_index
    ):

        motor_id = (
            self.motor_ids[
                motor_index
            ]
        )

        frame = tk.Frame(
            self.scrollable_frame,
            borderwidth=2,
            relief="groove",
            padx=8,
            pady=5,
            width=180,
            height=160,
            bg="SystemButtonFace"
        )

        frame.pack_propagate(
            False
        )

        checkbox = tk.Checkbutton(
            frame,
            variable=
            self.selected_motors[
                motor_index
            ],
            bg="white",
            command=
            lambda idx=motor_index:
            self.update_checkbox_color(
                idx
            )
        )

        checkbox.pack(
            side="top",
            anchor="w"
        )

        self.checkbox_refs[
            motor_index
        ] = checkbox

        motor_label = tk.Label(
            frame,
            text=f"Motor {motor_id}",
            font=("Arial", 9, "bold"),
            bg="SystemButtonFace"
        )

        motor_label.pack()

        state_label = tk.Label(
            frame,
            text="STOPPED",
            fg="gray",
            font=("Arial", 8),
            bg="SystemButtonFace"
        )

        state_label.pack()

        time_frame = tk.Frame(
            frame,
            bg="SystemButtonFace"
        )

        time_frame.pack(
            pady=3,
            fill="x",
            expand=True
        )

        # CW

        cw_frame = tk.Frame(
            time_frame,
            bg="SystemButtonFace"
        )

        cw_frame.pack(
            fill="x",
            pady=1
        )

        tk.Label(
            cw_frame,
            text="CW:",
            width=5,
            anchor="w",
            bg="SystemButtonFace"
        ).pack(
            side="left"
        )

        tk.Entry(
            cw_frame,
            textvariable=
            self.clockwise_vars[
                motor_index
            ],
            width=8
        ).pack(
            side="left",
            fill="x",
            expand=True
        )

        tk.Label(
            cw_frame,
            text="ms",
            bg="SystemButtonFace"
        ).pack(
            side="left"
        )

        # CCW

        ccw_frame = tk.Frame(
            time_frame,
            bg="SystemButtonFace"
        )

        ccw_frame.pack(
            fill="x",
            pady=1
        )

        tk.Label(
            ccw_frame,
            text="CCW:",
            width=5,
            anchor="w",
            bg="SystemButtonFace"
        ).pack(
            side="left"
        )

        tk.Entry(
            ccw_frame,
            textvariable=
            self.counterclockwise_vars[
                motor_index
            ],
            width=8
        ).pack(
            side="left",
            fill="x",
            expand=True
        )

        tk.Label(
            ccw_frame,
            text="ms",
            bg="SystemButtonFace"
        ).pack(
            side="left"
        )

        # Main buttons

        button_frame = tk.Frame(
            frame,
            bg="SystemButtonFace"
        )

        button_frame.pack(
            pady=3,
            fill="x"
        )

        tk.Button(
            button_frame,
            text="UP",
            command=
            lambda idx=motor_index:
            self.send_individual_up(
                idx
            ),
            bg="lightgreen"
        ).pack(
            side="left",
            padx=1,
            fill="x",
            expand=True
        )

        tk.Button(
            button_frame,
            text="DOWN",
            command=
            lambda idx=motor_index:
            self.send_individual_down(
                idx
            ),
            bg="lightcoral"
        ).pack(
            side="left",
            padx=1,
            fill="x",
            expand=True
        )

        # Quick buttons

        quick_frame = tk.Frame(
            frame,
            bg="SystemButtonFace"
        )

        quick_frame.pack(
            pady=2,
            fill="x"
        )

        tk.Button(
            quick_frame,
            text="+1s UP",
            command=
            lambda idx=motor_index:
            self.send_quick_up(
                idx
            ),
            bg="#90EE90"
        ).pack(
            side="left",
            padx=1,
            fill="x",
            expand=True
        )

        tk.Button(
            quick_frame,
            text="+1s DOWN",
            command=
            lambda idx=motor_index:
            self.send_quick_down(
                idx
            ),
            bg="#FFB6C1"
        ).pack(
            side="left",
            padx=1,
            fill="x",
            expand=True
        )

        frame.motor_index = (
            motor_index
        )

        frame.state_label = (
            state_label
        )

        frame.motor_label = (
            motor_label
        )

        frame.checkbox = (
            checkbox
        )

        self.motor_controls.append(
            frame
        )

        frame.bind(
            "<Button-1>",
            lambda event,
            idx=motor_index:
            self.toggle_motor_selection(
                idx
            )
        )

        self.update_checkbox_color(
            motor_index
        )

    # ============================================================
    # TIMINGS
    # ============================================================

    def load_times_from_file(self):

        if not os.path.exists(
            JSON_FILE
        ):

            self.timings_status_label.config(
                text="Timings: DEFAULT"
            )

            print(
                "No saved times found, using defaults."
            )

            return

        try:

            with open(
                JSON_FILE,
                "r"
            ) as f:

                data = json.load(f)

            for i, motor_id in enumerate(
                self.motor_ids
            ):

                if motor_id in data:

                    self.clockwise_vars[
                        i
                    ].set(
                        data[motor_id][
                            "clockwise"
                        ]
                    )

                    self.counterclockwise_vars[
                        i
                    ].set(
                        data[motor_id][
                            "counterclockwise"
                        ]
                    )

            self.timings_status_label.config(
                text="Timings: LOADED"
            )

            print(
                "Motor timings loaded."
            )

        except Exception as e:

            print(
                "Timing load error:",
                e
            )

            self.timings_status_label.config(
                text="Timings: ERROR"
            )

    def save_times_to_file(self):

        try:

            data = {}

            for i, motor_id in enumerate(
                self.motor_ids
            ):

                data[motor_id] = {

                    "clockwise":
                    self.clockwise_vars[
                        i
                    ].get(),

                    "counterclockwise":
                    self.counterclockwise_vars[
                        i
                    ].get()
                }

            with open(
                JSON_FILE,
                "w"
            ) as f:

                json.dump(
                    data,
                    f,
                    indent=4
                )

            self.timings_status_label.config(
                text="Timings: SAVED"
            )

            print(
                "Motor timings saved."
            )

        except Exception as e:

            print(
                "Timing save error:",
                e
            )

    def send_timings_to_arduino(self):

        if not connect_serial():

            print(
                "Arduino not connected."
            )

            return

        if not self.send_serial(
            "TIMINGS_START\n"
        ):

            return

        success_count = 0

        for i, motor_id in enumerate(
            self.motor_ids
        ):

            cw = (
                self.clockwise_vars[
                    i
                ].get()
            )

            ccw = (
                self.counterclockwise_vars[
                    i
                ].get()
            )

            command = (
                f"TIMINGS:"
                f"{motor_id}:"
                f"{cw}:"
                f"{ccw}\n"
            )

            if self.send_serial(
                command
            ):

                success_count += 1

            time.sleep(
                0.05
            )

        self.send_serial(
            "TIMINGS_END\n"
        )

        self.timings_status_label.config(
            text=
            f"Timings: SENT {success_count}/120"
        )

        print(
            f"Sent {success_count}/120 timings."
        )

    # ============================================================
    # SERIAL STATUS
    # ============================================================

    def check_serial_status(self):

        global ser

        try:

            if ser is not None and ser.is_open:

                self.connection_status.config(
                    text="Arduino: CONNECTED",
                    fg="green"
                )

                while ser.in_waiting:

                    try:

                        line = (
                            ser.readline()
                            .decode(
                                "ascii",
                                errors="ignore"
                            )
                            .strip()
                        )

                        if not line:
                            continue

                        print(
                            "Arduino:",
                            line
                        )

                        # ----------------------------
                        # ACK
                        # ----------------------------

                        if line.startswith(
                            "ACK:"
                        ):

                            command_id = (
                                line[4:]
                            )

                            self.command_status_label.config(
                                text=
                                f"Arduino ACK: "
                                f"Command {command_id}"
                            )

                        # ----------------------------
                        # START
                        # ----------------------------

                        elif line.startswith(
                            "START:"
                        ):

                            self.command_status_label.config(
                                text=
                                f"Arduino: {line}"
                            )

                        # ----------------------------
                        # DONE
                        # ----------------------------

                        elif line.startswith(
                            "DONE:"
                        ):

                            self.command_status_label.config(
                                text=
                                f"Arduino: {line}"
                            )

                        # ----------------------------
                        # ERROR
                        # ----------------------------

                        elif line.startswith(
                            "ERROR:"
                        ):

                            self.command_status_label.config(
                                text=
                                f"Arduino ERROR: {line}"
                            )

                        # ----------------------------
                        # TIMINGS
                        # ----------------------------

                        elif line.startswith(
                            "TIMINGS_STATUS:"
                        ):

                            self.timings_status_label.config(
                                text=line
                            )

                    except Exception:
                        break

            else:

                self.connection_status.config(
                    text="Arduino: DISCONNECTED",
                    fg="red"
                )

                connect_serial()

        except Exception as e:

            print(
                "Serial status error:",
                e
            )

        self.root.after(
            SERIAL_RECONNECT_MS,
            self.check_serial_status
        )

    # ============================================================
    # VISUAL STATES
    # ============================================================

    def update_visual_states(self):

        current_time = (
            time.time() * 1000
        )

        if (
            current_time -
            self.last_visual_update
            <
            VISUAL_UPDATE_MS
        ):

            self.root.after(
                VISUAL_UPDATE_MS,
                self.update_visual_states
            )

            return

        self.last_visual_update = (
            current_time
        )

        for i, frame in enumerate(
            self.motor_controls
        ):

            state = (
                self.motor_states[i]
            )

            if (
                state in [
                    "moving_up",
                    "moving_down"
                ]
                and
                current_time >=
                self.motor_end_times[i]
            ):

                self.motor_states[i] = (
                    "stopped"
                )

                state = "stopped"

            if state == "moving_up":

                frame_color = "#e8f5e8"

                state_text = (
                    "MOVING UP"
                )

                state_color = "green"

            elif state == "moving_down":

                frame_color = "#ffe8e8"

                state_text = (
                    "MOVING DOWN"
                )

                state_color = "red"

            else:

                if self.selected_motors[
                    i
                ].get():

                    frame_color = (
                        "#FFCCCC"
                    )

                else:

                    frame_color = (
                        "SystemButtonFace"
                    )

                state_text = (
                    "STOPPED"
                )

                state_color = "gray"

            if (
                frame.state_label.cget(
                    "text"
                )
                !=
                state_text
            ):

                frame.state_label.config(
                    text=state_text,
                    fg=state_color
                )

            if (
                frame.cget("bg")
                !=
                frame_color
            ):

                frame.config(
                    bg=frame_color
                )

                frame.state_label.config(
                    bg=frame_color
                )

                frame.motor_label.config(
                    bg=frame_color
                )

        self.root.after(
            VISUAL_UPDATE_MS,
            self.update_visual_states
        )

    # ============================================================
    # LAYOUT
    # ============================================================

    def update_layout(self):

        canvas_width = (
            self.canvas.winfo_width()
        )

        if canvas_width < 200:

            canvas_width = (
                self.root.winfo_width()
                - 50
            )

        control_width = 190

        controls_per_row = max(
            3,
            canvas_width //
            control_width
        )

        for widget in (
            self.scrollable_frame
            .winfo_children()
        ):

            widget.grid_forget()

        for i, control in enumerate(
            self.motor_controls
        ):

            row = (
                i //
                controls_per_row
            )

            col = (
                i %
                controls_per_row
            )

            control.grid(
                row=row,
                column=col,
                padx=5,
                pady=5,
                sticky="nsew"
            )

        for col in range(
            controls_per_row
        ):

            self.scrollable_frame.columnconfigure(
                col,
                weight=1
            )

    def on_resize(self, event):

        if event.widget != self.root:
            return

        if hasattr(
            self,
            "_resize_id"
        ):

            try:

                self.root.after_cancel(
                    self._resize_id
                )

            except Exception:
                pass

        self._resize_id = (
            self.root.after(
                500,
                self.update_layout
            )
        )

    def on_mouse_wheel(self, event):

        self.canvas.yview_scroll(
            -1 *
            int(
                event.delta / 120
            ),
            "units"
        )

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def on_close(self):

        global ser

        try:

            if self.voice_hotkey_hook:

                import keyboard

                keyboard.unhook(
                    self.voice_hotkey_hook
                )

        except Exception:
            pass

        try:

            if ser is not None and ser.is_open:

                # Stop motors before closing
                self.send_serial(
                    "CMD:9999:STOP:0:ALL\n"
                )

                time.sleep(
                    0.1
                )

                ser.close()

                print(
                    "Serial connection closed."
                )

        except Exception as e:

            print(
                "Shutdown error:",
                e
            )

        self.root.destroy()


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = MotorControlGUI(
        root,
        NUM_MOTORS
    )

    root.mainloop()

