import socket
import threading
import tkinter as tk 
from tkinter import scrolledtext

class ChatClient:
    def __init__(self, host='localhost', port=55555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((host, port))

        self.root = tk.Tk()
        self.root.title("Chat Room")
        self.root.configure(bg='#f0f0f0')  

        self.chat_area = scrolledtext.ScrolledText(self.root, width=60, height=20, wrap=tk.WORD, bg='#ffffff', font=('Arial', 11))
        self.chat_area.pack(padx=20, pady=10)
        self.chat_area.config(state='disabled')

        self.msg_entry = tk.Entry(self.root, width=50, bg='#ffffff', font=('Arial', 11))
        self.msg_entry.pack(padx=20, pady=5)

        self.send_button = tk.Button(self.root, text="Send", command=self.send_message, bg='#4caf50', fg='#ffffff', font=('Arial', 12), relief=tk.FLAT)
        self.send_button.pack(padx=20, pady=5)

        threading.Thread(target=self.receive_message).start()
        self.root.mainloop()

    def send_message(self):
        msg = self.msg_entry.get()
        if msg == "/exit":
            self.exit_chat()
        self.client.send(msg.encode('utf-8'))
        self.msg_entry.delete(0, tk.END)

    def receive_message(self):
        while True:
            try:
                msg = self.client.recv(1024).decode('utf-8')
                self.chat_area.config(state='normal')
                self.chat_area.insert('end', msg + '\n')
                self.chat_area.yview('end')
                self.chat_area.config(state='disabled')
            except:
                break

    def exit_chat(self):
        self.client.send("/exit".encode('utf-8'))
        self.root.quit()

if __name__ == "__main__":
    client = ChatClient()
