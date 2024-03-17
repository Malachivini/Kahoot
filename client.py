import tkinter as tk
from tkinter import messagebox, Toplevel  # Import the messagebox module
import socket
import threading
import json
from PIL import Image, ImageTk
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

#Code by Malachi Vinizky 209320563

# Server address and port
HOST = '127.0.0.1'
PORT = 65432
FORMAT = 'utf-8'

global_socket = None
# Variables to store the selected category and nickname
category_selected = " "
nickname = " "
root = None
time_left = 20
time_to_next = 10
Countdown_valid = False
client_Answered = False
latest_answer_options = []
last_question_number = None
currect_answer_index = None
kahoot_image = None
original_image = Image.open("kahoot.png")
resized_image = original_image.resize((200, 100))

crown_image = Image.open("crown.png")
crown_image = crown_image.resize((100, 100))
crown_photo = None


# Generate a key and IV (Initialization Vector)
key = b'\x04\x03|\xeb\x8dSh\xe0\xc5\xae\xe5\xe1l9\x0co\xca\xb1"\r-Oo\xbaiYa\x1e\xd1\xf7\xa2\xdf'
iv = b'#\xb59\xee\xa7\xc4@n\xe5r\xac\x97lV\xff\xf1'

# Function to encrypt plaintext using AES-CBC
def encrypt(plaintext):
    global FORMAT
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode(FORMAT)) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    return ciphertext

# Function to decrypt ciphertext using AES-CBC
def decrypt(ciphertext):
    global FORMAT
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
    return decrypted_data.decode(FORMAT)


# return a darker version of a color, for On_Click Purpose
def darken_color(hex_color, factor=0.7):
    # Convert hex color to RGB
    rgb = [int(hex_color[i:i+2], 16) for i in (1, 3, 5)]
    # Darken the RGB values
    darker_rgb = [int(c * factor) for c in rgb]
    # Convert back to hex
    return f"#{''.join(f'{c:02x}' for c in darker_rgb)}"

# Check if a message is JSON type
def is_json(myjson):
    try:
        json_object = json.loads(myjson)
    except ValueError as e:
        return False
    except json.JSONDecodeError as e:  # Specifically for Python 3.5+
        return False
    return True

# Function to connect to server
def connect_to_server():
    global global_socket
    try:
        # Initialize the socket as a TCP/IP socket
        global_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        global_socket.connect((HOST, PORT))
        print(f"Connected to {HOST}:{PORT}")
    except Exception as e:
        print(f"Connection error: {e}")



# Function to cleanly disconnect from the server
def disconnect_from_server():
    global global_socket
    try:
        if global_socket:
            print("Sending disconnect message to server...")
            if nickname == " ":
                global_socket.sendall(encrypt(json.dumps({"Disconnect": "Yes"})))
                global_socket.close()
            elif last_question_number: # Disconnect for Middle of game
                registration_data = json.dumps({"Disconnect": "Yes", "nickname": nickname, "category": category_selected, "question_number": last_question_number})
                global_socket.sendall(encrypt(registration_data))
            else: # Disconnect for Registration part
                registration_data = json.dumps({"Disconnect": "Yes", "nickname": nickname, "category": category_selected})
                global_socket.sendall(encrypt(registration_data))
            print("Disconnected from server.")
    except Exception as e:
        print(f"Error sending disconnect to Server {e}")


### Sum up GUI ###

# Adjust GUI height per amount of players
def calculate_window_height(player_count):
    base_height = 470  # Base height to account for title, images, and button
    per_player_height = 30  # Estimated height per player
    return base_height + (player_count * per_player_height)

def show_game_over_gui(scores, leaderboard):
    global resized_image, kahoot_image, crown_photo
    # GUI Base Values
    game_over_window = tk.Toplevel(root)
    game_over_window.title("Game Over")
    game_over_window.geometry(f"600x{calculate_window_height(len(scores))}")

    # Layout frames
    left_frame = tk.Frame(game_over_window)
    left_frame.pack(side="left", fill="both", expand=True)

    right_frame = tk.Frame(game_over_window)
    right_frame.pack(side="right", fill="y")

    # Leaderboard on the right
    leaderboard_label = tk.Label(right_frame, text="Leaderboard", font=("Segoe UI", 16))
    leaderboard_label.pack(pady=(20, 10))  # Adjust padding as needed

    # Create the Listbox with a Scrollbar
    scrollbar = tk.Scrollbar(right_frame)
    scrollbar.pack(side="right", fill="y")

    leaderboard_listbox = tk.Listbox(right_frame, yscrollcommand=scrollbar.set, width=30, background="#FAFAFA", fg="#212121")
    for entry in leaderboard:
        leaderboard_listbox.insert(tk.END, f"{entry['nickname']}: {entry['score']}")
    leaderboard_listbox.pack(side="left", fill="both", expand=True)

    scrollbar.config(command=leaderboard_listbox.yview)

    # Images for GUI
    resized_image = original_image.resize((50, 25))
    kahoot_image = ImageTk.PhotoImage(resized_image)
    crown_photo = ImageTk.PhotoImage(crown_image)
    # Kahoot image on the top left
    tk.Label(left_frame, image=kahoot_image).pack(side="top", anchor="nw")

    # Big label of "Game Over"
    tk.Label(left_frame, text="Game Over", font=("Segoe UI", 24)).pack(pady=20)

    # Crown image and label for the first place
    tk.Label(left_frame, image=crown_photo).pack(pady=10)
    first_place = max(scores.items(), key=lambda item: item[1])
    tk.Label(left_frame, text=f"{first_place[0]}: {first_place[1]}", font=("Segoe UI", 18)).pack()

    tk.Label(left_frame, text="", height=2).pack()  # Empty label as spacer

    # "Scores:" label
    tk.Label(left_frame, text="Scores:", font=("Segoe UI", 16)).pack()

    # List of all participants' scores in descending order
    scores_text = "\n".join([f"{name}: {score}" for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)])
    tk.Label(left_frame, text=scores_text, font=("Segoe UI", 14)).pack(pady=20)

    # "Restart" button
    restart_button = tk.Button(left_frame, text="Restart", command=lambda: restart_game(game_over_window))
    restart_button.configure(background='#004a7c', foreground='#ffffff')
    restart_button.pack(pady=20)


    # Disconnect when closing GUI
    game_over_window.protocol("WM_DELETE_WINDOW", lambda: on_gui_close(root))

    # When click restart, go to Registration GUI
    def restart_game(game_over_window):
        global nickname, category_selected, last_question_number, currect_answer_index, latest_answer_options
        # Reset global variables
        nickname = " "
        category_selected = " "
        last_question_number = None
        currect_answer_index = None
        latest_answer_options = []
        # Close the "Game Over" window
        game_over_window.destroy()

        create_gui()


# Start the Game Over GUI
def handle_game_over(data):
    scores = data["scores"]  # Assuming 'scores' is a dictionary of {participant_name: score}
    leaderboard = data["leaderboard_scores"]
    show_game_over_gui(scores, leaderboard)


### Game GUI ###
def open_game_gui():

    global nickname
    global category_selected
    global root
    global kahoot_image
    global resized_image
    # colors for buttons
    colors = [
        '#FFFFE0',  # light yellow
        '#ADD8E6',  # light blue
        '#98FB98',  # light green
        '#FFB6C1',  # light red
    ]

    # GUI Base Values
    game_window = Toplevel(root)
    game_window.title("Kahoot")
    game_window.geometry("800x500")
    game_window.configure(background='#FAFAFA')

    # Create a frame for the top part of the window
    top_frame = tk.Frame(game_window)
    top_frame.configure(background='#FAFAFA')
    top_frame.pack(side="top", fill="x")

    # Kahoot Image
    resized_image = original_image.resize((200, 100))
    kahoot_image = ImageTk.PhotoImage(resized_image)
    image_label = tk.Label(top_frame, image=kahoot_image)
    image_label.configure(background='#FAFAFA')
    image_label.pack(side="top", anchor="nw")

    # Chart for displaying Answers Count
    chart_canvas = tk.Canvas(game_window, width=400, height=200)
    chart_canvas.configure(background='#FAFAFA', borderwidth=0, highlightthickness=0)

    # score table for scores
    scores_label = tk.Text(game_window, height=10, width=50)


    # Kahoot Label
    tk.Label(game_window, text="Kahoot", background='#FAFAFA', font=("Segoe UI", 24)).pack(pady=10)


    # Placeholder for the countdown timer
    timer_label = tk.Label(game_window, text="20", font=("Segoe UI", 18))
    timer_label.configure(background='#FAFAFA')
    timer_label.pack(pady=5)

    # Placeholder for the question
    question_label = tk.Label(game_window, text="null", font=("Segoe UI", 16))
    question_label.configure(background='#FAFAFA')
    question_label.pack(pady=20)

    # Answer options (placeholders for now)
    answers_frame = tk.Frame(game_window)
    answers_frame.configure(background='#FAFAFA')
    answers_frame.pack(pady=10)
    answer_buttons = []
    for i in range(4):
        button = tk.Button(answers_frame, text="null", font=("Segoe UI", 14), bg=colors[i], width=15, height=2)
        button.grid(row=i//2, column=i%2, padx=5, pady=5)
        answer_buttons.append(button)

    def on_answer_click(answer_index, question_number):
        global nickname, category_selected, time_left, client_Answered
        answer_data = json.dumps({
            "action": "answer",
            "nickname": nickname,
            "category": category_selected,
            "question_number": question_number,
            "answer_index": answer_index,
            "time_left": time_left
        })
        client_Answered = True  # For when Countdown Gets to 0 - Do nothing

        global_socket.sendall(encrypt(answer_data))

        # Update button states: disable all and highlight the selected one
        for i, button in enumerate(answer_buttons):
            button.config(state=tk.DISABLED)  # Disable and reset color
            if i == answer_index:
                button.config(bg=darken_color(colors[i]))  # Highlight the selected button

    # Countdown for the current question
    def countdown(question_number):
        global time_left, nickname, category_selected, global_socket
        print(f"Time left {time_left}")
        if time_left > 0:
            timer_label.config(text=str(time_left))  # update countdown label
            time_left -= 1
            game_window.after(1000, countdown, question_number)  # Schedule the countdown function to run after 1 second
        elif not client_Answered:
            # Timer has reached zero, send a "no answer" message
            no_answer_data = json.dumps({
                "action": "answer",
                "nickname": nickname,
                "category": category_selected,
                "question_number": question_number,
                "answer_index": None,  # Indicates no answer was selected
                "time_left": 0
            })
            global_socket.sendall(encrypt(no_answer_data))

            # Disable Buttons to prevent answering the question after time is up
            for button in answer_buttons:
                button.config(state=tk.DISABLED)
        else:
            pass

    # Ask the Server for the next question given the index of the current one
    def request_next_question(last_question_number):
        request_data = json.dumps({
            "Next_question": "request_next_question",
            "last_question_number": last_question_number,
            "nickname": nickname,  # Ensure server knows who is asking
            "category": category_selected
        })
        global_socket.sendall(encrypt(request_data))

    # Different Countdown for the time between questions
    def start_scoring_countdown():
        global time_to_next, last_question_number, Countdown_valid
        print(f"Time to next left {time_to_next}")
        if time_to_next > 0:
            # Update the timer label with the time left in the scoring phase
            timer_label.config(text=str(time_to_next))
            time_to_next -= 1
            root.after(1000, start_scoring_countdown)  # Decrement the countdown after 1 second
        else:
            # Time's up for the scoring phase, proceed to the next step
            print("Times up")
            if Countdown_valid: # this is important in case another player already asked the Server For a new question
                request_next_question(last_question_number)
            else:
                print("Countdown not valid anymore")

    # Update Game GUI with the new question, and restart the Countdown
    def update_gui_with_question(question_number, question_text ,answers, game_window):
        global time_left, client_Answered, Countdown_valid
        full_question_text = f"Q{question_number + 1}: {question_text}"  # indexes start from 0
        # Update GUI data
        question_label.config(text=full_question_text)
        for i, button in enumerate(answer_buttons):
            button.config(text=answers[i], bg=colors[i], state=tk.NORMAL, command=lambda i=i: on_answer_click(i, question_number))
        client_Answered = False  # update the var from 'start_scoring_countdown' to indicate some player has asked for a new question already

        time_left = 20
        # reset and hide chart and score
        chart_canvas.delete("all")
        scores_label.delete(1.0, tk.END)
        scores_label.pack_forget()
        game_window.geometry("800x500")
        # start the countdown
        countdown(question_number)

    # Loop that handles Server messages during game
    def listen_for_server_messages_for_game():
        global global_socket, latest_answer_options, last_question_number, Countdown_valid
        try:
            while True:
                message = global_socket.recv(1024)
                print(message)
                if not message == b'':
                    message = decrypt(message)
                    if message:
                        data = json.loads(message)
                        if data["action"] == "question":  # if there is a new question
                            print(data)
                            # Update the GUI with the question and answers
                            latest_answer_options = data["answers"]
                            last_question_number = data["question_number"]
                            Countdown_valid = False
                            game_window.after(0, lambda: update_gui_with_question(data["question_number"], data["question_text"], data["answers"], game_window))
                            message = json.dumps({
                                "Update": "received_question",
                                "nickname": nickname,
                                "category": category_selected,
                                "question_number": data["question_number"],
                            })
                            global_socket.sendall(encrypt(message))
                        elif data["action"] == "summary":  # if there is a Summary of scores so far
                            print(data)
                            game_window.after(0, lambda:handle_summary_message(data))
                        elif data["action"] == "game_over":  # if the game is over
                            game_window.destroy()
                            handle_game_over(data)
                            break  # stop monitoring messages in here
                else:
                    break
        except Exception as e:
            print(f"Error receiving message from server: {e}")

    # handle the data given in the question summary
    def handle_summary_message(data):
        global time_left ,time_to_next, Countdown_valid
        chart_canvas.delete("all")
        answers_count = data["answers_count"]
        correct_answer_index = data.get("correct_answer_index")
        scores = data["scores"]

        # update Chart and Scores
        draw_chart(chart_canvas, answers_count, correct_answer_index)
        display_scores(scores)
        game_window.geometry("800x800")

        chart_canvas.pack(pady=(20, 0))
        scores_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))  # Move scores to the bottom

        # stop question clock
        time_left = 0
        timer_label.config(text=str(time_left))

        question_label.config(text="Get ready for the next question")

        # start 'time to next' countdown
        time_to_next = 5
        Countdown_valid = True  # this enables the first player who reaches 0 to send the server a request
        start_scoring_countdown()

    # create the chart of answers count
    def draw_chart(canvas, answers_count, correct_answer_index):
        global latest_answer_options
        bar_width = 50
        max_height = 150  # Maximum bar height
        spacing = 30  # Space between bars
        start_x = 50  # Starting X position for the first bar
        canvas_height = 180

        max_count = max(answers_count) if answers_count else 1  # Prevent division by zero
        for i, count in enumerate(answers_count):
            bar_height = (count / max_count) * max_height if max_count else 0
            x0 = start_x + i * (bar_width + spacing)
            y0 = canvas_height - bar_height  # Subtract bar height from canvas height to start drawing from bottom
            x1 = x0 + bar_width
            y1 = canvas_height

            # Draw the bar
            canvas.create_rectangle(x0, y0, x1, y1, fill=colors[i], outline="black")

            # Label for the bar
            label_text = f"{answers_count[i]}"

            # Adjust y position for the label to ensure it's below the bar
            label_y = y0 - 10  # Place the label 10 pixels above the bar
            label_color = 'green' if i == correct_answer_index else "black"  # Green for correct, black for others

            canvas.create_text(x0 + bar_width / 2, label_y, text=label_text, fill=label_color, anchor="s")

            # Create the label text below the bar for answer
            label_text = f"{latest_answer_options[i]}"
            label_y = canvas_height + 5
            canvas.create_text(x0 + bar_width / 2, label_y, text=label_text, anchor="n")

    # Add all scores in Descending order
    def display_scores(scores):
        scores_label.delete(1.0, tk.END)  # Clear existing content
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        scores_text = "\n".join([f"{name}: {score}" for name, score in sorted_scores])
        scores_label.insert(tk.END, scores_text)

    # listen to server on a different thread
    threading.Thread(target=listen_for_server_messages_for_game, args=(),daemon=True).start()

    # handle exit
    game_window.protocol("WM_DELETE_WINDOW", lambda: on_gui_close(root))




#### Ready GUI ####

# re-update the list of participants
def update_participants_list_gui(participants, participants_label, waiting_room):
    participants_label.config(text="\n".join(participants))
    waiting_room.geometry(f"400x{300 + len(participants)*20}")


# To use `update_participants_list_gui` safely from a background thread
def safe_update_participants_list(participants, waiting_room, participants_label):
    waiting_room.after(0, update_participants_list_gui, participants, participants_label, waiting_room)

# Loop to handle messages from server
def listen_for_server_messages(update_gui_callback, waiting_room, participants_label):
    global global_socket
    try:
        while True:
            message = global_socket.recv(1024)
            if not message == b'':
                message = decrypt(message)
                if is_json(message):
                    data = json.loads(message)
                    if data["action"] == "update":  # update list of participants
                        participants = data["participants"]
                        update_gui_callback(participants, waiting_room, participants_label)
                    elif data["action"] == "start_game":  # start the game
                        print("Start Game")
                        registration_data = json.dumps({"Start_Quiz": "Yes", "nickname": nickname, "category": category_selected})
                        global_socket.sendall(encrypt(registration_data))
                        waiting_room.destroy()  # close this window
                        open_game_gui()
                        break  # break out of loop
                elif message:  # If a simple string
                    print(message)
                else:
                    print("Received an empty message from server. Server may have closed the connection.")
                    break
            else:
                break
    except Exception as e:
        print(f"Error receiving message from server: {e}")

# upload waiting room GUI
def open_waiting_room():
    global nickname
    global category_selected
    global root
    global kahoot_image

    # GUI Base Values
    waiting_room = Toplevel(root)
    waiting_room.title("Waiting Room")
    waiting_room.geometry(f"400x300")

    # add elements
    top_frame = tk.Frame(waiting_room)
    top_frame.pack(side="top", fill="x", anchor="nw")
    tk.Label(waiting_room, text="Kahoot", font=("Segoe UI", 24)).pack(pady=10)
    tk.Label(waiting_room, text=f"Category: {category_selected}", font=("Segoe UI", 18)).pack(pady=5)

    kahoot_image = ImageTk.PhotoImage(resized_image)

    # Place the image in the top left corner
    image_label = tk.Label(top_frame, image=kahoot_image)
    image_label.pack(side="left", anchor="nw")

    participants_label = tk.Label(waiting_room, text="", font=("Segoe UI", 14), justify=tk.LEFT)
    participants_label.pack(pady=10)

    # if you click start, tell the server and send the data
    def on_start_click():
        start_button.config(bg='#98FB98', state=tk.DISABLED)  # Change color and disable the button
        # Construct and send the readiness message to the server
        readiness_data = json.dumps({"action": "ready", "nickname": nickname, "category": category_selected})
        global_socket.sendall(encrypt(readiness_data))

    start_button = tk.Button(waiting_room, text="Start", font=("Segoe UI", 16), bg='SystemButtonFace', command=on_start_click)
    start_button.configure(background='#004a7c', foreground='#ffffff')
    start_button.pack(pady=20)

    # handle server messages on a different thread
    threading.Thread(target=listen_for_server_messages, args=(safe_update_participants_list, waiting_room, participants_label), daemon=True).start()
    waiting_room.protocol("WM_DELETE_WINDOW", lambda: on_gui_close(root))


#### Register GUI ####

def register_and_listen(enter_GUI):
    global nickname
    global category_selected
    try:
        registration_data = json.dumps({"nickname": nickname, "category": category_selected})
        global_socket.sendall(encrypt(registration_data))

        # Wait for server response to registration
        response = decrypt(global_socket.recv(1024))

        if response == "Nickname already taken":
            messagebox.showerror("Registration Error", "Nickname already taken. Please choose another.")
        elif response == "Registration successful":
            enter_GUI.destroy()
            open_waiting_room()
        elif response == "This quiz has already started. please wait":
            messagebox.showerror("Registration Error", response)
        else:
            print(f"Server response: {response}")
    except Exception as e:
        print(f"Error during registration or communication: {e}")


# handle registering nickname
def on_register_click(nickname_entry, selected_category, registration_gui):
    # Get the nickname and category from the GUI elements
    global nickname
    global category_selected
    nickname = nickname_entry.get()
    category_selected = selected_category.get()
    if nickname:
        print(f"Nickname: {nickname}")

    # Start the registration and listening in a background thread
    threading.Thread(target=register_and_listen, args=(registration_gui,), daemon=True).start()


# Function to handle GUI close event
def on_gui_close(root):
    disconnect_from_server()  # Ensure disconnection from the server
    root.destroy()  # Then destroy the GUI window


# Create the main window
def create_gui():
    # GUI Base Values
    global root, resized_image, kahoot_image

    registration_gui = Toplevel(root)
    registration_gui.title("Kahoot")
    registration_gui.geometry("400x300")  # Adjusted for additional radio buttons

    selected_category = tk.StringVar(value="Math")  # Initialize with default category
    top_frame = tk.Frame(registration_gui)
    top_frame.pack(side="top", fill="x", anchor="nw")
    kahoot_label = tk.Label(registration_gui, text="Kahoot", font=("Segoe UI", 24))
    kahoot_label.pack(pady=10)

    resized_image = original_image.resize((50, 25))
    kahoot_image = ImageTk.PhotoImage(resized_image)

    # Place the image in the top left corner
    image_label = tk.Label(top_frame, image=kahoot_image)
    image_label.pack(side="left", anchor="nw")

    # Define radio button options
    categories = ["Math", "Riddle", "History"]

    # Create and pack radio buttons for category selection
    for category in categories:
        tk.Radiobutton(registration_gui, text=category, variable=selected_category, value=category).pack()

    # Entry for nickname
    nickname_entry = tk.Entry(registration_gui, font=("Segoe UI", 14), width=20)
    nickname_entry.pack(pady=5)

    register_button = tk.Button(registration_gui, text="Register", font=("Segoe UI", 14), command=lambda: on_register_click(nickname_entry, selected_category, registration_gui))
    register_button.configure(background='#004a7c', foreground='#ffffff')
    register_button.pack(pady=10)

    registration_gui.protocol("WM_DELETE_WINDOW", lambda: on_gui_close(root))



def log_in_GUI():
    global root
    def attempt_login():
        username = username_entry.get()
        password = password_entry.get()
        connect_to_server()
        print(f"Attempting to log in with username: {username} and password: {password}")
        if send_login_credentials(username, password):
            root.withdraw()
            create_gui()
        else:
            messagebox.showerror("Log In Error", "Username or Password Invalid, please try again")

    # Create the main window
    root = tk.Tk()
    root.title("Login")
    root.geometry("300x300")  # Width x Height
    root.configure(background='#f0f0f0')

    # Label "Kahoot"
    kahoot_label = tk.Label(root, text="Kahoot", font=("Segoe UI", 20))
    kahoot_label.pack(pady=(10, 5))  # Add some vertical padding

    # Label "Please log in"
    login_label = tk.Label(root, text="Please log in", font=("Segoe UI", 14))
    login_label.pack(pady=(5, 10))  # Add some vertical padding

    # Entry for username
    username_label = tk.Label(root, text="Username:")
    username_label.pack()
    username_entry = tk.Entry(root, font=("Segoe UI", 12))
    username_entry.pack()

    # Entry for password
    password_label = tk.Label(root, text="Password:")
    password_label.pack()
    password_entry = tk.Entry(root, font=("Segoe UI", 12), show="*")  # 'show="*"' masks the password
    password_entry.pack()

    # "Log in" button
    login_button = tk.Button(root, text="Log In", command=attempt_login)
    login_button.configure(background='#004a7c', foreground='#ffffff')
    login_button.pack(pady=10)

    def send_login_credentials(username, password):
        try:
            login_data = json.dumps({"action": "login", "username": username, "password": password})
            global_socket.sendall(encrypt(login_data))
            # Wait for server response
            response = decrypt(global_socket.recv(1024))
            response_data = json.loads(response)
            return response_data.get("status") == "success"
        except Exception as e:
            print(f"Error sending login credentials: {e}")
            return False

    # Start the Tkinter event loop
    root.mainloop()


#### main code ####

log_in_GUI()

