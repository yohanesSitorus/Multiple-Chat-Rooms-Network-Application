import select
import socket
import threading
import json

class ChatServer:
    def __init__(self, host='localhost', port=55555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen()
        self.rooms = {}  # {room_name: [client_socket1, client_socket2, ...]}
        self.room_created_by = {}  # {room_name: client_socket1, ...]}
        self.clients = {}  # {client_socket: client_name, ...}
        self.kicked_clients = {} # {client_socket: 1, ...}
        self.user_credentials = self.load_credentials()

    def load_credentials(self):
        try:
            with open("credentials.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_credentials(self):
        with open("credentials.json", "w") as f:
            json.dump(self.user_credentials, f)  

    def handle_client(self, client_socket, client_address):
        while True:
            client_socket.send(f"Welcome to the chat room!\n".encode('utf-8'))
            client_socket.send("Enter 'login' to login or 'register' to register: ".encode('utf-8'))
            choice = client_socket.recv(1024).decode('utf-8').strip().lower()

            if choice == "login":
                if self.login(client_socket):
                    break
            elif choice == "register":
                if self.register(client_socket):
                    break
                
        client_name = self.clients[client_socket]
        self.broadcast_to_main_lobby(f"{client_name} has joined the server.".encode('utf-8'), client_socket)
        self.enter_main_lobby(client_socket, client_name)

    def login(self, client_socket):
        client_socket.send("Enter your username: ".encode('utf-8'))
        username = client_socket.recv(1024).decode('utf-8').strip()

        client_socket.send("Enter your password: ".encode('utf-8'))
        password = client_socket.recv(1024).decode('utf-8').strip()

        if username in self.user_credentials and self.user_credentials[username] == password:
            self.clients[client_socket] = username
            client_socket.send("Login successful!\n".encode('utf-8'))
            return True
        else:
            client_socket.send("Invalid credentials. Try again.\n".encode('utf-8'))
            return False

    def register(self, client_socket):
        client_socket.send("Enter your desired username: ".encode('utf-8'))
        username = client_socket.recv(1024).decode('utf-8').strip()
        client_socket.send("Enter your desired password: ".encode('utf-8'))
        password = client_socket.recv(1024).decode('utf-8').strip()

        if username in self.user_credentials:
            client_socket.send("Username already exists. Try again.\n".encode('utf-8'))
            return False
        else:
            self.user_credentials[username] = password
            self.save_credentials()
            self.clients[client_socket] = username
            client_socket.send("Registration successful!\n".encode('utf-8'))
            return True      

    def enter_main_lobby(self, client_socket, client_name):
        # greeting
        client_socket.send(f"\nWelcome to the main lobby, {client_name}!\n".encode('utf-8'))

        # ask for command
        client_socket.send("Available commands:\n".encode('utf-8'))
        client_socket.send("/create <room_name> - create a new room\n".encode('utf-8'))
        client_socket.send("/join <room_name> - join a room\n".encode('utf-8'))
        client_socket.send("/close <room_name> - close a room\n".encode('utf-8'))
        client_socket.send("/rooms - show available rooms\n".encode('utf-8'))
        client_socket.send("/room - <room_name> - see who is in the room\n".encode('utf-8'))
        client_socket.send("/kick <username> - kick a user from the room\n".encode('utf-8'))
        client_socket.send("/exit - exit the chat app\n".encode('utf-8'))

        # show available rooms
        client_socket.send("\nAvailable rooms:\n".encode('utf-8'))
        if self.rooms:
            for room in self.rooms:
                client_socket.send(f"{room}\n".encode('utf-8'))
        else:
            client_socket.send("No rooms available.".encode('utf-8'))

        room_name = None
        is_in_room = False
        while True:
            command = self.get_valid_command(client_socket)
            if command.startswith('/create '):
                room_name = command.split(' ', 1)[1]
                if room_name in self.rooms:
                    client_socket.send(f"Room '{room_name}' already exists. Try joining it.".encode('utf-8'))
                else:
                    self.rooms[room_name] = []
                    self.room_created_by[room_name] = client_socket
                    self.broadcast_to_main_lobby(f"New room has been created by {client_name}: {room_name}".encode('utf-8'), None)
            elif command.startswith('/join '):
                room_name = command.split(' ', 1)[1]
                if room_name in self.rooms:
                    is_in_room = True
                    break
                else:
                    client_socket.send(f"Room '{room_name}' does not exist. Please join another room.".encode('utf-8'))
            elif command == '/rooms':
                if self.rooms:
                    client_socket.send("Available rooms:".encode('utf-8'))
                    for room in self.rooms:
                        client_socket.send(f"{room}\n".encode('utf-8'))
                else:
                    client_socket.send("No rooms available.".encode('utf-8'))
            elif command.startswith('/room '):
                room_name = command.split(' ', 1)[1]
                if room_name in self.rooms:
                    client_socket.send(f"Room '{room_name}' members:".encode('utf-8'))
                    for client_socket_in_room in self.rooms[room_name]:
                        client_socket.send(f"{self.clients[client_socket_in_room]}\n".encode('utf-8'))
                else:
                    client_socket.send(f"Room '{room_name}' does not exist. Try again.".encode('utf-8'))
            elif command.startswith('/close '):
                room_name = command.split(' ', 1)[1]

                # check if room exists
                if room_name in self.rooms:
                    # check if client is the creator of the room
                    if client_socket == self.room_created_by[room_name]:
                        self.broadcast_to_main_lobby(f"Room '{room_name}' has been closed by {client_name}.".encode('utf-8'), None)
                        self.broadcast_to_room(f"Room '{room_name}' has been closed by {client_name}.".encode('utf-8'), room_name, None)

                        # put all clients in the room in the kicked_clients dictionary
                        for client_socket_in_room in self.rooms[room_name]:
                            self.kicked_clients[client_socket_in_room] = 1
                        del self.rooms[room_name]
                        del self.room_created_by[room_name]
                    else:
                        client_socket.send(f"You are not authorized to close room '{room_name}'.".encode('utf-8'))
                else:
                    client_socket.send(f"Room '{room_name}' does not exist. Try again.".encode('utf-8'))
            elif command.startswith('/kick '):
                # check if client is the creator of the room
                if client_socket == self.room_created_by[room_name]:
                    username_to_kick = command.split(' ', 1)[1]
                    kicked_socket = None
                    for client_socket_in_room in self.rooms[room_name]:
                        if self.clients[client_socket_in_room] == username_to_kick:
                            kicked_socket = client_socket_in_room
                            break
                    if kicked_socket:
                        kicked_username = self.clients[kicked_socket]
                        self.broadcast_to_room(f"{kicked_username} has been kicked from the room by {client_name}.".encode('utf-8'), room_name, None)
                        kicked_socket.send("You have been kicked from the room.".encode('utf-8'))
                        self.kicked_clients[kicked_socket] = 1  # add to kicked_clients dictionary
                        client_socket.send(f"You have kicked {kicked_username} from the room.".encode('utf-8'))
                    else:
                        client_socket.send(f"User '{username_to_kick}' not found in the room.".encode('utf-8'))
                else:
                    client_socket.send("You are not authorized to kick users from this room.".encode('utf-8'))
            elif command == '/exit':
                self.exit_chat_app(client_socket)
                break
            else:
                client_socket.send(f"Command not found. Try again.".encode('utf-8'))

        if is_in_room:
            self.enter_room(client_socket, client_name, room_name)

    def get_valid_command(self, client_socket):
        while True:
            command = client_socket.recv(1024).decode('utf-8').strip()

            if command.startswith('/create '):
                return command
            elif command.startswith('/join '):
                return command
            elif command == '/rooms':
                return command
            elif command.startswith('/room '):
                return command
            elif command.startswith('/kick '):
                return command
            elif command.startswith('/close '):
                return command
            elif command == '/exit':
                return command
            else:
                client_socket.send("Command not found. Try again.".encode('utf-8'))

    def enter_room(self, client_socket, client_name, room_name):
        # add client to the room
        self.rooms[room_name].append(client_socket)
        client_socket.send(f"Welcome to {room_name}, {client_name}!".encode('utf-8'))
        
        current_members = "Current members in the room: " + ", ".join(self.clients[client] for client in self.rooms[room_name]) + "\n"
        client_socket.send(current_members.encode('utf-8'))
        client_socket.send("To exit the room, type '/exit'".encode('utf-8'))
        
        # broadcast to the room that a new client has joined
        self.broadcast_to_room(f"{client_name} has joined the room.".encode('utf-8'), room_name, client_socket)
        
        flag = self.listen_for_messages(client_socket, room_name, client_name)

        if flag == "exit":
            self.enter_main_lobby(client_socket, client_name)
        else:
            self.remove_client(client_socket)

    def listen_for_messages(self, client_socket, room_name, client_name):
        while True:
            try:
                ready_to_read, _, _ = select.select([client_socket], [], [], 1)  
                if ready_to_read:
                    msg = client_socket.recv(1024)
                    if msg:
                        if msg.decode('utf-8').strip().lower() == '/exit':
                            self.exit_room(room_name, client_socket)
                            return "exit"  # break the loop
                        else:
                            self.broadcast_to_room(f"{client_name}: ".encode('utf-8') + msg, room_name, None)
                    else:
                        return "error"
                else:
                    # check if client is in the kicked_clients dictionary. If so, exit them from the room
                    if client_socket in self.kicked_clients:
                        del self.kicked_clients[client_socket]
                        self.exit_room(room_name, client_socket)
                        return "exit"  # break the loop
                    continue
            except:
                return "error"   # break the loop
            

    def broadcast_to_main_lobby(self, msg, sender_socket):
        for client_socket in self.clients:
            if client_socket != sender_socket:
                is_in_room = False
                for client_sockets in self.rooms.values():
                    if client_socket in client_sockets:
                        is_in_room = True
                        break
                if not is_in_room:
                    try:
                        client_socket.send(msg)
                    except:
                        self.remove_client(client_socket)

    def broadcast_to_room(self, msg, room_name, sender_socket):
        for client_socket in self.rooms[room_name]:
            if client_socket != sender_socket:
                try:
                    client_socket.send(msg)
                except:
                    self.remove_client(client_socket)

    def exit_room(self, room_name, client_socket):
        client_name = self.clients[client_socket]
        try:
            room =  self.rooms.get(room_name, None)
            if room:
                room.remove(client_socket)
            self.broadcast_to_room(f"{client_name} has left the room.".encode('utf-8'), room_name, None)
        except:
            pass

    def exit_chat_app(self, client_socket):
        client_name = self.clients[client_socket]
        self.broadcast_to_main_lobby(f"{client_name} has left the server.".encode('utf-8'), client_socket)
        del self.clients[client_socket]
        client_socket.close()

    def remove_client(self, client_socket):
        try:
            if client_socket in self.clients:
                room_name = next((room for room in self.rooms if client_socket in self.rooms[room]), None)
                client_name = self.clients[client_socket]
                self.rooms[room_name].remove(client_socket)
                del self.clients[client_socket]
                self.broadcast_to_room(f"{client_name} has left the room.".encode('utf-8'), room_name, None)
                client_socket.close()
        except:
            pass

    def run(self):
        print("Server started...")
        while True:
            client_socket, client_address = self.server.accept()
            print(f"New connection from {client_address}")
            threading.Thread(target=self.handle_client, args=(client_socket, client_address)).start()

if __name__ == "__main__":
    server = ChatServer()
    server.run()
