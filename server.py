import socket
import threading
from enum import Enum, auto
import json
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import xml.etree.ElementTree as ET

#Code by Malachi Vinizky 209320563

# Server settings
HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on
FORMAT = 'utf-8'

# Track the number of connected clients
connected_clients = 0

# Generate a key and IV (Initialization Vector)
key = b'\x04\x03|\xeb\x8dSh\xe0\xc5\xae\xe5\xe1l9\x0co\xca\xb1"\r-Oo\xbaiYa\x1e\xd1\xf7\xa2\xdf'
iv = b'#\xb59\xee\xa7\xc4@n\xe5r\xac\x97lV\xff\xf1'

# path to DB in xml format
db_file = "DB.xml"

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


def check_credentials(username, password):
    tree = ET.parse('DB.xml')
    root = tree.getroot()

    # Navigate to the credentials section
    credentials_section = root.find('credentials')

    # Iterate over all user elements
    for user in credentials_section.findall('user'):
        user_name = user.find('username').text
        user_password = user.find('password').text

        # Check if the provided credentials match
        if user_name == username and user_password == password:
            return True

    return False


# get all scores from category on leaderboard
def get_leaderboard_scores(category_name):
    tree = ET.parse('DB.xml')
    root = tree.getroot()
    root = root.find('scores')

    leaderboard_scores = []
    for category in root.findall('category'):
        if category.attrib['name'] == category_name:
            for score in category.findall('score'):
                nickname = score.find('nickname').text
                points = int(score.find('points').text)
                leaderboard_scores.append((nickname, points))

    # Sort the scores in descending order
    leaderboard_scores.sort(key=lambda x: x[1], reverse=True)
    return leaderboard_scores

# Add score to DB
def add_score_to_category(db_file, category_name, nickname, score):
    tree = ET.parse(db_file)
    root = tree.getroot()

    # Find or create the category element
    category = root.find(f".//category[@name='{category_name}']")
    if category is None:
        category = ET.SubElement(root, "category", name=category_name)

    # Add the new score
    score_element = ET.SubElement(category, "score")
    ET.SubElement(score_element, "nickname").text = nickname
    ET.SubElement(score_element, "points").text = str(score)

    # Save changes back to the XML file
    tree.write(db_file)


# Update when there are changes in the participants list
def broadcast_participants(quiz):
    participants_list = [participant.nickname for participant in quiz.participants]
    data = json.dumps({"action": "update", "participants": participants_list})
    for client in quiz.participants:
        client.conn.sendall(encrypt(data))


# Check if all participants ready to start
def all_players_ready(quiz):
    return all(participant.ready for participant in quiz.participants)


# When all ready, start quiz
def handle_ready_message(quiz):
    if all_players_ready(quiz):
        start_game_message = json.dumps({"action": "start_game"}) + "\n"
        for participant in quiz.participants:
            participant.conn.sendall(encrypt(start_game_message))


# Send next question
def handle_request_next_question(data, quiz):
    if not quiz.isNextQuestion:
        quiz.isNextQuestion = True
        last_question_number = data["last_question_number"]
        quiz.isOn = False
        if last_question_number + 1 < len(quiz.questions):
            # There are more questions
            next_question_number = last_question_number + 1
            send_question_to_all_participants(quiz, next_question_number)
        else:
            # No more questions, game over
            send_game_over_to_all_participants(quiz)


# When game is over, handle sent message to clients and reset vars
def send_game_over_to_all_participants(quiz):
    # Update leaderboard with participants' score
    for participant in quiz.participants:
        add_score_to_category(db_file, quiz.category.name, participant.nickname, participant.score)

    scores = {participant.nickname: participant.score for participant in quiz.participants}
    leaderboard_scores = get_leaderboard_scores(quiz.category.name)
    formatted_leaderboard_scores = [{'nickname': nick, 'score': score} for nick, score in leaderboard_scores]
    game_over_data = json.dumps({
        "action": "game_over",
        "scores": scores,
        "leaderboard_scores" :  formatted_leaderboard_scores
    })
    for participant in quiz.participants:
        participant.conn.sendall(encrypt(game_over_data))

    # Reset vars
    quiz.isNextQuestion = False
    quiz.isOn = False
    quiz.participants.clear()
    for qu in quiz.questions:
        qu.answers_count = [0,0,0,0]


# When all answered, update all client this question result
def send_summary_to_all_participants(quiz, current_question_number):
    current_question = quiz.questions[current_question_number]
    summary_data = json.dumps({
        "action": "summary",
        "answers_count": current_question.answers_count,
        "correct_answer_index": current_question.correct_answer_index,
        "scores": {p.nickname: p.score for p in quiz.participants}
    })
    for participant in quiz.participants:
        participant.conn.sendall(encrypt(summary_data))
        participant.answered = False  # Reset for the next question


# handle participant answer
def handle_answer(quiz, participant_nickname, question_number, answer_index, time_left):
    question = quiz.questions[question_number]

    # Find the participant object
    participant = next((p for p in quiz.participants if p.nickname == participant_nickname), None)
    if participant:
        participant.answered = True  # Mark the participant as having answered

        # Update the answers_count
        if answer_index is not None:
            question.answers_count[answer_index] += 1

        # Check if the answer is correct and time_left is positive
        if answer_index == question.correct_answer_index and time_left > 0:
            participant.score += time_left  # Update score based on time left

    # Check if all participants have answered
    if all(p.answered for p in quiz.participants):
        send_summary_to_all_participants(quiz, question_number)


# Send question to all participants
def send_question_to_all_participants(quiz, question_index):
    if not quiz.isOn: # id this is the first one asks
        quiz.isOn = True
        if question_index < len(quiz.questions):
            # Retrieve the specified question based on the index
            question = quiz.questions[question_index]

            # Prepare the question data to be sent
            question_data = json.dumps({
                "action": "question",
                "question_number": question_index,
                "question_text": question.question_text,
                "answers": question.answers
            })

            # Send the question data to all participants in the quiz
            for participant in quiz.participants:
                try:
                    print(f"sent to {participant.nickname} question {question_index}")
                    participant.conn.sendall(encrypt(question_data))
                except Exception as e:
                    print(f"Error sending question to participant {participant.nickname}: {e}")
        else:
            print(f"Invalid question index: {question_index}")


# Main function, deals with clients data
def handle_client(conn, addr):
    global connected_clients
    print(f"New connection from {addr}")
    connected_clients += 1
    print(f"Number of connected clients: {connected_clients}")

    try:
        while True:  # Keep the connection open for ongoing communication
            data = decrypt(conn.recv(1024))
            print(data)
            # Process the data received from the client
            if 'nickname' in data and 'category' in data:
                print(data)
                registration_data = json.loads(data)
                nickname = registration_data['nickname']
                category = registration_data['category']

                # Find the quiz for the category and add the participant
                # 'category' is the string received from the client

                if category in category_mapping:
                    category_enum = category_mapping[category]
                    quiz = next((q for q in quizzes if q.category == category_enum), None)
                if 'Disconnect' in data:  # if asks to disconnect, remove from relevant places
                    deleted = quiz.remove_participant_by_nickname(nickname)
                    broadcast_participants(quiz)
                    print(f"Participant {nickname} has logged out {deleted}")
                    if quiz.isOn:
                        if len(quiz.participants) == 0:
                            send_game_over_to_all_participants(quiz)
                            break
                        else:
                            if all(p.answered for p in quiz.participants):
                                # quiz.isOn = False
                                send_summary_to_all_participants(quiz, registration_data["question_number"])

                    else:
                        handle_ready_message(quiz)

                    conn.close()
                    break
                elif "Start_Quiz" in data:
                    send_question_to_all_participants(quiz, 0)
                elif "Next_question" in data:
                    handle_request_next_question(json.loads(data), quiz)
                elif "Update" in data:
                    quiz.isNextQuestion = False
                elif 'action' in data:
                    message = json.loads(data)
                    if message["action"] == "ready":
                        if quiz:
                            # Update participant's ready status
                            participant = next((p for p in quiz.participants if p.nickname == nickname), None)
                            if participant:
                                participant.ready = True
                            print(f"Participant {nickname} is ready")
                        response = f"Participant {nickname} is ready"
                        conn.sendall(encrypt(response))
                        handle_ready_message(quiz)
                    elif message["action"] == "answer":
                        handle_answer(quiz, nickname, message["question_number"], message["answer_index"], message["time_left"])
                elif quiz:
                    # Check if nickname is already taken
                    if any(participant.nickname == nickname for participant in quiz.participants):
                        response = "Nickname already taken"
                        conn.sendall(encrypt(response))
                    elif quiz.isOn:  # quiz has already started by other players
                        response = "This quiz has already started. please wait"
                        conn.sendall(encrypt(response))

                    else:
                        participant = Participant(nickname, category_enum, conn)
                        quiz.add_participant(participant)
                        response = "Registration successful"
                        conn.sendall(encrypt(response))
                        broadcast_participants(quiz)
                else:
                    response = "Invalid category"
                    conn.sendall(encrypt(response))

            elif "action" in data:
                message = json.loads(data)
                username = message["username"]
                password = message["password"]
                if check_credentials(username, password):
                    response = json.dumps({"status": "success"})
                else:
                    response = json.dumps({"status": "fail"})
                    break
                conn.sendall(encrypt(response))
            elif not data or data["Disconnect"] == 'Yes':
                break  # stop loop
            else:
                print("else")
                pass
    except Exception as e:
        print(f"Error handling client {addr}: {e}")

    # Client disconnecting
    connected_clients -= 1
    print(f"Client {addr} disconnected")
    print(f"Number of connected clients: {connected_clients}")
    conn.close()


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            # Start a new thread to handle the client
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()


class Category(Enum):
    Math = 1
    Riddle = 2
    History = 3


category_mapping = {
    'Math': Category.Math,
    'Riddle': Category.Riddle,
    'History': Category.History,
}


class Question:
    def __init__(self, category, question_text, answers, correct_answer_index, answerCount):
        self.category = category
        self.question_text = question_text
        self.answers = answers
        self.correct_answer_index = correct_answer_index
        self.answers_count = answerCount


class Participant:
    def __init__(self, nickname, category, conn):
        self.nickname = nickname
        self.category = category
        self.conn = conn
        self.ready = False
        self.answered = False
        self.score = 0


class Quiz:
    def __init__(self, category):
        self.category = category
        self.participants = []
        self.questions = []
        self.isOn = False
        self.isNextQuestion = False

    def add_participant(self, participant):
        self.participants.append(participant)

    def add_question(self, question):
        self.questions.append(question)

    def remove_participant_by_nickname(self, nickname):
        # Find the participant by nickname
        participant_to_remove = next((p for p in self.participants if p.nickname == nickname), None)
        # If found, remove them from the list
        if participant_to_remove:
            self.participants.remove(participant_to_remove)
            return True  # Successfully removed
        return False  # Participant not found


# Global list of quizzes, one for each category
quizzes = [Quiz(category) for category in Category]

# Create all questions
math_questions = [
    Question(Category.Math, "What is 2+2?", ["3", "4", "5", "6"], 1, [0,0,0,0]),
    Question(Category.Math, "What is the square root of 16?", ["2", "4", "8", "16"], 1, [0,0,0,0]),
    Question(Category.Math, "What is 5 * 5?", ["10", "20", "25", "30"], 2, [0,0,0,0]),
    Question(Category.Math, "What is 100 / 5?", ["5", "10", "20", "25"], 2, [0,0,0,0])
]

riddle_questions = [
    Question(Category.Riddle, "Steve's Mom has 3 sons: Avraham, Itzhak and...?", ["Ya'akov", "Steve", "Mohamad", "Son"], 1, [0,0,0,0]),
    Question(Category.Riddle, "If you are my son, But I'm not your Father, I am your?", ["Brother", "Sister", "Son", "Mother"], 3, [0,0,0,0]),
    Question(Category.Riddle, "What gets more wet while it dries you?", ["Towel", "Orange", "Museum", "Earth"], 0, [0,0,0,0])
]

history_questions = [
    Question(Category.History, "How long was the Six Days War?", ["6 Days", "1 Year", "7 Days", "50 Days"], 0, [0,0,0,0]),
    Question(Category.History, "In which year did the Titanic sink?", ["1923", "1905", "1898", "1912"], 3, [0,0,0,0]),
    Question(Category.History, "Which civilization is known for building pyramids?", ["Aztecs", "Romans", "Egyptians", "Greeks"], 2, [0,0,0,0]),
    Question(Category.History, "Who was the famous queen of ancient Egypt?", ["Nefertiti", "Cleopatra", "Hatshepsut", "Meritaten"], 1, [0, 0, 0, 0]),
    Question(Category.History, "Which city was the first capital of the United States?", ["Philadelphia", "Washington D.C.", "New York", "Boston"], 2, [0, 0, 0, 0])
]

if __name__ == '__main__':

    # upload question to quizzes
    math_quiz = next((quiz for quiz in quizzes if quiz.category == Category.Math), None)
    if math_quiz:
        for question in math_questions:
            math_quiz.add_question(question)
    history_quiz = next((quiz for quiz in quizzes if quiz.category == Category.History), None)
    if history_quiz:
        for question in history_questions:
            history_quiz.add_question(question)
    riddle_quiz = next((quiz for quiz in quizzes if quiz.category == Category.Riddle), None)
    if riddle_quiz:
        for question in riddle_questions:
            riddle_quiz.add_question(question)

    start_server()

