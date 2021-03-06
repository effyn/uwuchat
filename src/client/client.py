import asyncio
import asyncio.exceptions as async_exc
import os
import tkinter as tk
from traceback import print_exc

if os.name == 'nt':
    import winsound
    def playsound(filename: str):
        winsound.PlaySound(filename, winsound.SND_ASYNC)
else:
    def playsound(*args, **kwargs): return


class Client(tk.Tk):
    '''
    Simple uwuchat client implementation.
    '''

    MESSAGE_DELIMITER = b'\n'

    def __init__(self, host='hazel.cafe', port=8888, name='anon'):
        # init Tcl + Toplevel widget
        super().__init__()

        # client options
        self.host = host
        self.port = port
        self.name = name
        self.mention_str = f'@{name}'

        # how fast Tcl can update
        self.gui_timeout = 0.001

        # asyncio items, assigned when Client.run() is executed
        self.loop: asyncio.AbstractEventLoop = None
        self.net_task: asyncio.Task = None
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

        # state + tkinter config
        self.protocol("WM_DELETE_WINDOW", self.stop)
        self.iconbitmap('./assets/client-icon.ico')
        self.wm_title("uwuchat")
        self.wm_state('zoomed')
        self.wm_minsize(width=954, height=507)
        self.bind('<Configure>', self._configure_binding)

        width, height = self.winfo_width(), self.winfo_height()

        # root style
        self.config(
            bg = '#202225'
        )

        # channels/participants, just some space for now
        self.left_pane = tk.Frame(
            bg = '#2F3136',
            width = width // 6,
            height = height
        )
        self.main_pane = tk.Frame(
            bg = '#36393F',
            width = width - width // 3,
            height = height
        )
        self.right_pane = tk.Frame(
            bg = '#2F3136',
            width = width // 6,
            height = height
        )

        # tkinter widgets
        self.messages = tk.Text(
            master = self.main_pane,
            state = 'disabled',
            font = 'Consolas 12',
            fg = 'white',
            bg = '#36393F',
            width = 100,
            height = height // 18 - 8,
            #borderwidth = 0
        )
        self.entry = tk.Text(
            master = self.main_pane,
            font = 'Consolas 12',
            fg = 'white',
            bg = '#40444B',
            width = 71, # nearly 1:1 margins with side pane width
            height = 3
        )
        self.entry.bind("<Return>", self._entry_binding)

        self.messages.place(anchor='n', relx=0.5)
        self.entry.place(anchor='s', relx=0.5, rely=0.975)

    def place_all(self):
        '''
        Display the application's widgets.
        '''
        self.left_pane.place(anchor='nw')
        self.main_pane.place(anchor='n', relx=0.5)
        self.right_pane.place(anchor='ne', relx=1)

    async def send(self, data: bytes):
        '''
        Sends data to the server.
        '''
        print(f"[send] sending {data}...")
        self.writer.write(data)
        await self.writer.drain()
        print(f"[send] {data} sent")

    async def recv(self) -> bytes:
        '''
        Receives data from the server.
        '''
        print("[recv] waiting for data...")
        data = await self.reader.readuntil(Client.MESSAGE_DELIMITER)
        print(f"[recv] received {data}")
        return data

    def log(self, message: str, important=True):
        '''
        Appends messages to the messages `Listbox`.
        
        Messages default as `important`, scrolling down to the new message.
        '''
        self.messages.config(state='normal')
        self.messages.insert("end", message + '\n')
        self.messages.config(state='disabled')

        if important:
            self.messages.see("end")

    def _configure_binding(self, event):
        pass#self.messages.config(height = self.winfo_height() / 19 - self.entry['height'] - 1)

    def _entry_binding(self, event):
        '''
        Called when `<Return>` is pressed in the `Client.entry` Text widget.

        Schedules message data for transmission.
        '''
        if self.writer is None or self.writer.is_closing():
            return "break"

        # message has its leading and trailing whitespace stripped first
        if (message := self.entry.get("1.0", "end").strip()) != "":
            # then the user config attribute is joined with the message and encoded to bytes
            data = f"{self.name}: {message}\n".encode()
            print(f"[_entry_binding] scheduling send task for data {data}...")
            self.loop.create_task(self.send(data))

        self.after_idle(self.entry.delete, "1.0", "end")
        return "break"

    async def net(self, host, port):
        '''
        Connect to a `host` and `port` and start network logic.

        This is called as a result of calling `Client.run` so you shouldn't need to call this manually.
        '''
        try:
            while True:
                self.log(f"[info] connecting to host {host} on port {port}...")
                self.reader, self.writer = await asyncio.open_connection(host, port)
                self.log("[info] connected")

                while not (self.reader.at_eof() or self.writer.is_closing()):
                    data = await self.recv()
                    # TODO : this is pretty naive, need to implement filters
                    message = data.decode()[:-1]
                    if self.focus_get() is None:
                        if self.mention_str in message:
                            playsound('./assets/mention.wav')
                        else:
                            playsound('./assets/message.wav')
                    self.log(message)

                self.log("[error] server connection closed")
                self.writer.close()

        except asyncio.CancelledError:
            self.log("[info] quitting...")
            if not self.writer.is_closing():
                self.writer.close()
            await self.writer.wait_closed()

        except:
            print_exc()

    def stop(self):
        '''
        Cancels the network task, which stops the event loop cleanly.
        '''
        self.net_task.cancel()

    async def _async_run(self):
        '''
        Sets up asyncio-related stuff and starts updating Tcl.
        '''
        # asyncio stuff
        self.loop = asyncio.get_running_loop()
        self.outbox = asyncio.Queue()

        # use client config to create the network task
        self.net_task = asyncio.create_task(self.net(self.host, self.port))

        # draw the GUI at least once so that info/errors can be posted to the messages Listbox
        self.place_all()
        self.update()

        # update GUI until the net task is cancelled, use async wrapper to execute scheduled asyncio tasks first
        while not self.net_task.done():
            await asyncio.sleep(self.gui_timeout, self.update())

        # wait for the net task to finish after it is cancelled so that the writer object is closed properly
        await self.net_task

    def run(self):
        '''
        Runs the client application.
        '''
        asyncio.run(self._async_run())

if __name__ == "__main__":
    client = Client()
    client.run()
