# Microcline is a hackable, single-file micro-framework for CLI applications,
# optimized for text adventure games. Requires Python 3.10+.
#
# Features:
#   * Papers over the messiness of curses so you don't have to deal with it
#   * Simple and easy facilities for printing formatted text
#   * Navigable message and command history with intelligent coloration
#   * A built-in debugger
#
# Basic usage:
#
#     from microcline import Window
#     with Window() as window:
#       window.set_title("Basic Window")
#       window.say("Nice window you've got there!")
#       input = window.prompt("What are you waiting for?")
#
# See the runnable examples below for more.
#
# To enable debug mode, either initialize the window with `debug=True`
# or set the MICROCLINE_DEBUG environment variable.
#
# Debug mode enables the following features:
# 1. Press Ctrl+D at any time to enter an interactive debug session
#    that allows you to inspect and edit global state.
# 2. If the window exits with an exception, you will have the option
#    to enter an interactive debug session as above.
# 3. If the command box receives an unhandled key,
#    it will print the key code (and key name, if well-known).

# This demonstrates basic window creation, using the `with` keyword
# to manage the window context, dynamically setting the window title,
# and using the `say` and `prompt` convenience functions.
def example_basic():
  with Window() as window:
    window.set_title("Basic Window")
    window.say("Nice window you've got there!")
    input = window.prompt("What are you waiting for?")
    window.say("Fascinating!")
    input = window.prompt("Well, goodbye!")

# This demonstrates window configuration, command registration, colored output,
# message sigils, and manual window drawing.
# Observe how past messages automatically become dim.
# Try paging with page up/page down, navigating the command history
# with up/down, entering debug mode with Ctrl+D, and executing the
# registered custom command with Ctrl+R.
def example_advanced():
  with Window(height=24, width=80, title="Advanced Window", debug=True) as win:
    cmd = win.cmdbox
    msg = win.msgbox
    cmd.register(18, lambda w: w.say("You whistle softly."))  # 18 is Ctrl+R

    while True:
      msg.append("You are standing in a ", ("bright forest", win.green), ".")
      msg.append("You see a ", ("chalice", win.yellow), " sitting on a stump.")
      msg.append("You see a ", ("rude goblin", win.red), " nearby.", sigil="!")
      msg.draw()
      input = win.prompt("What do you do?")
      msg.append(f"You {input} with gusto.")

import curses

class Window:
  def __init__(self, height=None, width=None, title="", debug=False):
    import os
    self.debug_mode = False
    if debug or os.environ.get("MICROCLINE_DEBUG"):
      self.debug_mode = True
      
    self.init_h = height
    self.init_w = width
    self.title = title
  
  # __enter__ and __exit__ facilitate the `with` statement for context management.
  # A window can only be used within a context manager
  # in order to ensure that cleanup happens properly.
  def __enter__(self):
    try:  # this ensures __exit__ cleans up even if __enter__ panics
      self.screen = curses.initscr()  # initialize curses
  
      override_terminal_defaults()
      
      # Enables colors, but also messes up all the color values.
      curses.start_color() 
      
      # This allows us to use -1 in color pairs to refer to the default color.
      # It also fixes some (but not all) colors messed up by the previous step.
      curses.use_default_colors()
  
      # Fix the messed-up color values.
      curses.init_color(curses.COLOR_RED, 1000, 0, 0)
      curses.init_color(curses.COLOR_GREEN, 0, 1000, 0)
      curses.init_color(curses.COLOR_BLUE, 0, 0, 1000)
      curses.init_color(curses.COLOR_CYAN, 0, 1000, 1000)
      curses.init_color(curses.COLOR_YELLOW, 1000, 1000, 0)
      curses.init_color(curses.COLOR_MAGENTA, 1000, 0, 1000)
  
      # It's not enough to initialize colors,
      # to actually use them you have to associate integer
      # values with a combination of foreground and background color.
      self.white = curses.color_pair(0)  # predefined
      curses.init_pair(1, curses.COLOR_RED, -1)  # -1 means "terminal default"
      self.red = curses.color_pair(1)
      curses.init_pair(2, curses.COLOR_GREEN, -1)
      self.green = curses.color_pair(2)
      curses.init_pair(3, curses.COLOR_BLUE, -1)
      self.blue = curses.color_pair(3)
      curses.init_pair(4, curses.COLOR_CYAN, -1)
      self.cyan = curses.color_pair(4)
      curses.init_pair(5, curses.COLOR_MAGENTA, -1)
      self.magenta = curses.color_pair(5)
      curses.init_pair(6, curses.COLOR_YELLOW, -1)
      self.yellow = curses.color_pair(6)
  
      # The cursor should only be visible while we're in the input loop.
      # This causes some light cursor flickering,
      # but sadly there's no other way to prevent the cursor from jumping
      # all over the place.
      curses.curs_set(0)

      # Curses will crash if the configured window dimensions are
      # larger than the underlying terminal dimensions.
      # We prevent that crash by overriding the specified dimensions
      # if they're larger than the underlying terminal.
      # Also, height is weird here because we want it to represent the
      # "logical" height of our window, but in fact we have to initialize
      # the window with a height of +1 or else curses will crash after it
      # writes a full line to the bottom line in the window, as it attempts
      # to automatically wrap the cursor to the next (non-existent) line.
      (term_h, term_w) = self.screen.getmaxyx()

      if self.init_h:
        self.h = min(term_h-1, self.init_h)
      else:
        self.h = term_h-1

      if self.init_w:
        self.w = min(term_w, self.init_w)
      else:
        self.w = term_w

      # This defines the the parent window and its boundaries.
      # Height is a lie because of curses, see prior comment.
      self.box = self.screen.derwin(self.h+1, self.w, 0, 0)
  
      # Subwindows that we can independently clear and write to,
      # defined as relative children of the parent window.
      self.msgbox = Msgbox(self, self.h-4, self.w-2, 1, 0)
      self.cmdbox = Cmdbox(self, 1, self.w-4, self.h-2, 2)

      self.draw_border()
    except Exception as e:
      self.__exit__(e)
    
    return self
  
  def __exit__(self, *args):
    # It's crucial that this gets called in all circumstances,
    # because if not it will completely mess up the user's terminal
    # even after the program has ended.
    reset_terminal_defaults()
    if self.debug_mode and args[0]:  # args[0] != None indicates an exception
      import sys
      import traceback
      print("microcline window exited with an exception:")
      traceback.print_exc()  # manually print traceback
      inspect = input("Open a console to inspect global state? [y/N] ")
      if inspect.lower() == "y":
        debug_interactive()
      return True  # swallow the exception to avoid printing traceback twice

  # Draw the window borders.
  def draw_border(self):
    self.box.erase()

    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓ top of message box
    self.box.addstr(0, 0, "┏" + "━"*(self.w-2) + "┓")
    # ┣━━━━━━━━━━━━━━━━━━━━━━━━━━┫ border between message box and command box
    self.box.addstr(self.h-3, 0, "┣" + "━"*(self.w-2) + "┫")
    # ❱                            command box prompt
    self.box.addstr(self.h-2, 0, "❱")
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛ bottom of command box
    self.box.addstr(self.h-1, 0, "┗" + "━"*(self.w-2) + "┛")

    if self.title != "":
      # TODO: handle overlong titles
      # ┏━━━━━━━━━┫ Title ┣━━━━━━━━┓ title atop message box
      self.box.addstr(0, int(self.w/2 - len(self.title)/2) - 2, "┫ ")
      self.box.addstr(self.title, curses.A_BOLD)
      self.box.addstr(" ┣")
      
    self.box.refresh()

  def set_title(self, title):
    self.title = title
    self.draw_border()

  # A convenience method for adding new messages to the message window.
  # Note that this function redraws the message window with each call,
  # so if you want to add multiple lines it will be more efficient
  # to use window.msgbox.append (which does not redraw the window)
  # and call and window.msgbox.draw when you are ready to redraw.
  # Otherwise unnecessary screen flashing may occur.
  def say(self, message):
    self.msgbox.append(message)
    self.msgbox.draw()

  def prompt(self, prompt):
    return self.cmdbox.get(prompt)

# The subwindow where messages are displayed.
class Msgbox:
  def __init__(self, parent, h, w, y, x):
    self.h = h
    self.w = w
    self.parent = parent
    # Width is a lie to prevent curses crashes.
    self.box = self.parent.box.derwin(self.h, self.w+1, y, x)
    # The amount by which the output scrolls when paging.
    self.page_size = self.h // 3
    # Keeps track of where we're paged to.
    self.history_index = 0

    # In order to store the scrollback history,
    # we uses a bounded deque to emulate a ring buffer.
    from collections import deque
    self.history = deque(maxlen=self.h*10)

  # The first step to writing some new output to the msgbox
  # is appending it to the history buffer via this function.
  # Each line in the history buffer is a list of "chunks".
  # A chunk is either a string, or a 2-tuple consisting of
  # a string and a curses style attribute.
  # Spaces are not automatically inserted between chunks.
  # A sigil is prepended to each logical line to indicate
  # what sort of message it is: "·" for ordinary lines,
  # "❰" for prompts, "❱" for commands, "✖" for errors.
  # A line's sigil can be overridden via an optional parameter.
  #
  # Example:
  #   window.msgbox.append("You see a ", ("goblin", window.green), ".")
  def append(self, *chunks, sigil="·"):
    # Create a new entry at the front of the history buffer for the message
    # and prepend the sigil to the first line of the output.
    self.history.appendleft([(f"{sigil} ", curses.A_NORMAL)])
    line_position = 2

    for chunk in chunks:
      if type(chunk).__name__ == "str":
        phrase = chunk
        style = curses.A_NORMAL
      elif type(chunk).__name__ == "tuple":
        phrase = chunk[0]
        style = chunk[1]
      else:
        raise Exception("Can't append chunk of type f{type(chunk).__name__}")
      
      # Append the current phrase to the current line.
      # If this phrase takes us past the end of the line,
      # break it intelligently across as many lines as needed.
      while True:
        if line_position == 2:  # if we're at the beginning of the current line
          phrase = phrase.lstrip()  # remove leading whitespace

        remaining_space = self.w - line_position

        # Happy path, phrase doesn't overflow the current line.
        if len(phrase) <= remaining_space:
          self.history[0].append((phrase, style))
          line_position += len(phrase)
          break

        # Handle the overflow case.
        last_space = phrase[:remaining_space].rfind(" ")  # find rightmost space
        if last_space > 0:  # there are spaces in range to split on
          phrase_fragment = phrase[:last_space]
          self.history[0].append((phrase_fragment, style))
          phrase = phrase[last_space:]
        elif line_position == 2:  # single word longer than entire line
          phrase_fragment = phrase[:remaining_space]  # just split the word
          self.history[0].append((phrase_fragment, style))
          phrase = phrase[remaining_space:]
        # else we don't print anything on this line and try again on next line

        self.history.appendleft([("  ", curses.A_NORMAL)]) # start a new line
        line_position = 2
    
  # This is what updates the terminal with the output buffer.
  def draw(self):
    # The cursor should only be drawn during the input loop,
    # but sometimes the input loop calls this function,
    # so turn off the cursor to be safe.
    curses.curs_set(0)

    self.box.erase()

    # Stale messages get printed in desaturated color.
    # A message is stale if it is older than the most recent input,
    # and if we're not paging.
    stale = False
    line_style = curses.A_NORMAL
    
    # Lines need to shift up in the presence of the paging indicator.
    compensate_paging = 0
    if self.history_index != 0:
      # Write the paging indicator.
      self.box.addstr(self.h - 1, self.w // 2, "…")
      compensate_paging = 1
      
    # Don't print more than the size of the box,
    # or more than the number of lines of history we have.
    lines_to_print = min(
      self.h - compensate_paging,  # if paging, one less line of screen height
      len(self.history) - self.history_index
    )
    
    for i in range(0, lines_to_print):
      # Outside the inner loop to prevent most recent command from being stale.
      if stale:
        line_style = curses.A_DIM
      # Start at the bottom of the box, -1 to account for zero-indexing,
      # another -1 if we're paging, and -1 for each line already printed.
      self.box.move(self.h - 1 - compensate_paging - i, 0)
      line = self.history[i + self.history_index]
      for (phrase, chunk_style) in line:
        # The first sigil we see indicates the most recent command input,
        # and all lines above this one should render as dim,
        # though not if we're paging.
        if self.history_index == 0 and phrase[0] == "❱":
          stale = True  # will take effect on the next iteration
        self.box.addstr(phrase, chunk_style | line_style)  # union of styles

    self.box.refresh()
  
  def page_up(self):
    if len(self.history)-self.history_index > self.page_size:
      self.history_index += self.page_size
      self.draw()
  
  def page_down(self):
    if self.history_index >= self.page_size:
      self.history_index -= self.page_size
      self.draw()

# The subwindow where commands are typed.
class Cmdbox:
  def __init__(self, parent, h, w, y, x):
    self.h = h
    self.w = w
    self.chars = []
    self.custom_commands = {}
    self.parent = parent
    self.box = self.parent.box.derwin(self.h, self.w, y, x)
    self.box.keypad(True)  # interpret special keys as numeric values

    # Bounded deque to emulate a ring buffer.
    from collections import deque
    self.history = deque(maxlen=10)

  def get(self, prompt=None):
    if prompt != None:
      self.parent.msgbox.append(prompt, sigil="❰")
      self.parent.msgbox.draw()

    self.chars = []
    history_index = -1

    # Manual key-by-key input handling.
    while True:
      # Make sure the cursor is in the cmdbox before we turn it on again.
      self.box.move(*self.box.getyx())
      curses.curs_set(2)  # the only place where the cursor is enabled

      k = self.box.getch()
      match k:  # numeric value of the pressed key
        case key if 32 <= key <= 126:  # printable ascii range
          self.chars.append(chr(key))
          self.draw()
        case 127 | curses.KEY_BACKSPACE:  # curses sometimes forgets what 127 is
          if len(self.chars) != 0:
            self.chars.pop()  # erase last char
            self.draw()
        case curses.KEY_UP:
          if history_index < len(self.history)-1:
            history_index += 1
            self.chars = self.history[history_index].copy()
            self.draw()
        case curses.KEY_DOWN:
          if history_index > 0:
            history_index -= 1
            self.chars = self.history[history_index].copy()
            self.draw()
        case curses.KEY_PPAGE:
          self.parent.msgbox.page_up()
        case curses.KEY_NPAGE:
          self.parent.msgbox.page_down()
        case 13:  # enter
          break
        case 4:  # Ctrl+D, drop into interactive terminal
          if self.parent.debug_mode:
            reset_terminal_defaults()
            debug_interactive()
            override_terminal_defaults()
            self.parent.screen.refresh()  # bring curses window back
        case key if key in self.custom_commands:  # see the register function
          self.custom_commands[key](self.parent)
        case key:
          if self.parent.debug_mode:
            name = ""
            if curses.has_key(key):
              name = f" ({curses.keyname(key).decode()})"
            msg = f"unhandled key: {key}{name}"
            self.parent.msgbox.append(msg, sigil="✖")
            self.parent.msgbox.draw()
    
    curses.curs_set(0)  # make sure cursor is disabled again
    command = "".join(self.chars).lstrip()

    if command != "":
      self.box.erase()
      self.parent.msgbox.append((command, curses.A_BOLD), sigil="❱")

      # Don't remember identical consecutive actions.
      if len(self.history) == 0:
          self.history.appendleft(self.chars)
      else:
        if self.chars != self.history[0]: 
          self.history.appendleft(self.chars)

    self.chars = []
    self.draw()

    return command

  def draw(self):
    if len(self.chars) < self.w:
      self.box.erase()
      self.box.addstr(0, 0, "".join(self.chars))
    else:
      partial = "".join(self.chars[-(self.w - 2):])
      self.box.addstr(0, 0, f"…{partial}")

  # Register a custom function to run whenever the key
  # specified by `val` is pressed.
  # The function that is passed in must take a single parameter,
  # which is a reference to the window object that contains
  # the command box.
  # In order to determine which value corresponds to a given key,
  # enable debug mode and press the key at the command prompt.
  # For example, to bind a command to Ctrl+R, which has a value of 18:
  #     window.cmdbox.register(18, lambda w: w.say("Hello!"))
  def register(self, val, func):
    self.custom_commands[val] = func

# We need to disable some of curses' default behaviors.
# These settings will mess up the underlying terminal,
# so reset_terminal_defaults() should be used to reverse them.
def override_terminal_defaults():
  curses.noecho()  # don't echo every typed key
  curses.nonl()  # don't translate the enter key to newlines
  curses.cbreak()  # don't buffer inputs

# Be sure to always call reset_terminal_defaults() before exiting,
# including in the case of crashes.
def reset_terminal_defaults():
  curses.nocbreak()
  curses.nl()
  curses.echo()
  curses.endwin()  # closes the curses screen (can be undone by screen.refresh)
  
# Interactive debugger, usable when in debug mode.
def debug_interactive():
  import code
  console = code.InteractiveConsole(locals=globals())
  console.interact(banner="Remember to import the modules you need.\nUse `pprint(foo)` to pretty-print long things.\nPress Ctrl+D to return to the application.", exitmsg="")

# Convenience function for pretty-printing in debug mode.
def pprint(*args):
  import pprint
  pp = pprint.PrettyPrinter(indent=2)
  pp.pprint(*args)

if __name__ == "__main__":
  example_advanced()
