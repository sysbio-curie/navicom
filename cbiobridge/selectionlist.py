#########################################################################################
# selectionlist.py
# By Mathurin Dorel
# A dropping menu to select from a list
#########################################################################################

import tkinter as tk

MENU_WIDTH = 20
MENU_HEIGHT = 2

class SelectionList():

    def __init__(self, master, label, options, values=list()):
        """
        Initialize a SelectionList to choose between a set of options

        Args:
            master (widget): A tkinter widget to host the list.
            options (list): A list of options which are available with the list.
            values (list): Values to match to the options. If empty, values is set to options.
        """
        if (len(values) == 0):
            values = options
        else:
            assert len(options) == len(values), "'options' and 'values' must have the same length"
        assert all([ type(options[ii])==type(options[0]) for ii in range(len(options)) ]), ValueError("All options must have the same type")
        self._master = master
        self._label = tk.Label(master, text=label)
        self._label.pack()
        # dict matching options to values
        self._values = dict()
        for ii in range(len(values)):
            self._values[options[ii]] = values[ii]
        # Initialise the drop list button
        self._current = tk.StringVar()
        self._current.set(options[0])
        self._button = tk.Menubutton(master, textvariable=self._current, relief=tk.RAISED)
        self._button.config(height=MENU_HEIGHT, width=MENU_WIDTH)
        # Create the stored variable
        if (isinstance(options[0], str)):
            self._var = tk.StringVar()
        elif (isinstance(options[0], int)):
            self._var = tk.IntVar()
        elif (isinstance(options[0], float)):
            self._var = tk.FloatVar()
        # Create the selection menu
        self._selection = tk.Menu(self._button)
        for entry in options:
            self._selection.add_radiobutton(label=entry, value=entry, variable=self._var, command=self.update)
        # Bind the menu to the drop button
        self._button["menu"] = self._selection
        self._button.pack()

    def get(self):
        """ Get the selected value """
        return(self._values[self._var.get()])
    
    def value(self):
        """ Get the selected value """
        self.get()
    
    def update(self):
        """ Update the text on the button """
        self._current.set(self._var.get())
        print(self.get())

