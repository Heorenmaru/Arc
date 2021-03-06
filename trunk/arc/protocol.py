# Arc is copyright 2009-2012 the Arc team and other contributors.
# Arc is licensed under the BSD 2-Clause modified License.
# To view more details, please see the "LICENSING" file in the "docs" folder of the Arc Package.

import cPickle, datetime, hashlib, os, traceback, shutil

from twisted.internet import reactor
from twisted.internet.protocol import Protocol

from arc.constants import *
from arc.globals import *
from arc.irc_client import ChatBotFactory
from arc.playerdata import *

class ArcServerProtocol(Protocol):
    """
    Main protocol class for communicating with clients.
    Commands are mainly provided by plugins (protocol plugins).
    """

    def connectionMade(self):
        "We've got a TCP connection, let's set ourselves up."
        # We use the buffer because TCP is a stream protocol :)
        self.buffer = ""
        self.loading_world = False
        self.logger = self.factory.logger
        self.settings = {}
        # Set identification variable to false
        self.identified = False
        # Get an ID for ourselves
        try:
            self.id = self.factory.claimId(self)
        except ServerFull:
            if not self.isHelper():
                self.sendError("The server is full.")
                return
            # Check for IP bans
        self.ip = self.transport.getPeer().host
        if self.factory.isIpBanned(self.ip):
            self.sendError("You are banned: %s" % self.factory.ipBanReason(ip))
            return
        self.factory.logger.debug("Assigned ID %i" % self.id)
        self.sent_first_welcome = False
        self.read_only = False
        self.username = None
        self.selected_archive_name = None
        self.initial_position = None
        self.last_block_changes = []
        self.last_block_position = (-1, -1, -1)
        self.frozen = False

    def queueTask(self, task, data=[], world=None):
        "Adds the given task to the factory's queue."
        # If they've overridden the world, use that as the client.
        if world:
            self.factory.queue.put((world, task, data))
        else:
            self.factory.queue.put((self, task, data))

    def connectionLost(self, reason):
        # Leave the world
        try:
            self.factory.leaveWorld(self.world, self)
        except (KeyError, AttributeError):
            pass
            # Remove ourselves from the username list
        if self.username:
            self.factory.recordPresence(self.username)
            try:
                if self.factory.usernames[self.username.lower()] is self:
                    del self.factory.usernames[self.username.lower()]
            except KeyError:
                pass
        # Remove from ID list, send removed msgs
        self.factory.releaseId(self.id)
        self.factory.queue.put((self, TASK_PLAYERLEAVE, (self.id,)))
        if self.username:
            self.factory.logger.info("Disconnected '%s'" % (self.username))
            self.factory.runHook("playerQuit", {"client": self})
            self.factory.logger.debug("(reason: %s)" % (reason))
        self.connected = 0

    def send(self, data):
        self.transport.write(data)

    def sendPacked(self, mtype, *args):
        fmt = TYPE_FORMATS[mtype]
        self.transport.write(chr(mtype) + fmt.encode(*args))

    def sendError(self, error):
        self.factory.logger.info("Sending error: %s" % error)
        self.sendPacked(TYPE_ERROR, error)
        reactor.callLater(0.2, self.transport.loseConnection)

    def isOwner(self):
        return self.factory.isOwner(self.username.lower())

    def isDirector(self):
        return self.factory.isDirector(self.username.lower()) or self.isOwner()

    def isAdmin(self):
        return self.factory.isAdmin(self.username.lower()) or self.isDirector()

    def isMod(self):
        return self.factory.isMod(self.username.lower()) or self.isAdmin()

    def isHelper(self):
        return self.factory.isHelper(self.username.lower()) or self.isMod()

    def isWorldOwner(self):
        return (self.username.lower() == self.world.status["owner"].lower()) or self.isHelper()

    def isOp(self):
        return (self.username.lower() in self.world.ops) or self.isWorldOwner()

    def isBuilder(self):
        return (self.username.lower() in self.world.builders) or self.isOp()

    def isSpectator(self):
        return self.factory.isSpectator(self.username.lower())

    def isSilenced(self):
        return self.factory.isSilenced(self.username.lower())

    def canEnter(self, world):
        if not world.status["private"] and not world.isWorldBanned(self.username.lower()):
            return True
        else:
            return self.isBuilder()

    def dataReceived(self, data):
        "Called when data is received over the socket."
        # First, add the data we got onto our internal buffer
        self.buffer += data
        # While there's still data there...
        while self.buffer:
            # Examine the first byte, to see what the command is
            type = ord(self.buffer[0])
            try:
                format = TYPE_FORMATS[type]
            except KeyError:
                # it's a weird data packet, probably a ping.
                reactor.callLater(0.2, self.transport.loseConnection)
                return
                # See if we have all its data
            if len(self.buffer) - 1 < len(format):
                # Nope, wait a bit
                break
            # OK, decode the data
            parts = list(format.decode(self.buffer[1:]))
            self.buffer = self.buffer[len(format) + 1:]
            if type == TYPE_INITIAL:
                # Get the client's details
                protocol, self.username, mppass, utype = parts
                if self.identified == True:
                    self.factory.logger.info("Kicked '%s'; already logged in to server" % (self.username))
                    self.sendError("You already logged in!")
                # Right protocol?
                if protocol != 7:
                    self.sendError("Wrong protocol.")
                    break
                # Check their password
                correct_pass = hashlib.md5(self.factory.salt + self.username).hexdigest()[-32:].strip("0")
                mppass = mppass.strip("0")
                if not self.transport.getHost().host.split(".")[0:2] == self.ip.split(".")[0:2]:
                    if mppass != correct_pass:
                        self.factory.logger.info(
                            "Kicked '%s'; invalid password (%s, %s)" % (self.username, mppass, correct_pass))
                        self.sendError("Incorrect authentication, please try again.")
                        return
                value = self.factory.runHook("prePlayerConnect", {"client": self})
                if not value and value != None: return
                self.factory.logger.info("Connected, as '%s'" % self.username)
                self.identified = True
                # Are they banned?
                if self.factory.isBanned(self.username):
                    self.sendError("You are banned: %s" % self.factory.banReason(self.username))
                    return
                # OK, see if there's anyone else with that username
                if not self.factory.duplicate_logins and self.username.lower() in self.factory.usernames:
                    self.factory.usernames[self.username.lower()].sendError("You logged in on another computer.")
                self.factory.usernames[self.username.lower()] = self
                self.factory.joinWorld(self.factory.default_name, self)
                # Send them back our info.
                self.sendPacked(
                    TYPE_INITIAL,
                    7, # Protocol version
                    packString(self.factory.server_name),
                    packString(self.factory.server_message),
                    100 if (self.isOp() if hasattr(self, "world") else False) else 0,
                )
                # Then... stuff
                for client in self.factory.usernames.values():
                    client.sendServerMessage("%s has come online." % self.username)
                if self.factory.irc_relay:
                    self.factory.irc_relay.sendServerMessage("07%s has come online." % self.username)
                reactor.callLater(0.1, self.sendLevel)
                reactor.callLater(1, self.sendKeepAlive)
                self.data = PlayerData(self) # Create a player data object
                self.settings["tpprotect"] = self.data.bool("misc", "tpprotect") # Get their teleport protection setting
                self.factory.runHook("onPlayerConnect", {"client": self}) # Run the player connect hook
            elif type == TYPE_BLOCKCHANGE:
                x, y, z, created, block = parts
                if self.identified == False:
                    self.factory.logger.info("Kicked '%s'; did not send a login before building" % (self.ip))
                    self.sendError("Provide an authentication before building.")
                    return
                if block == 255:
                    block = 0
                if block > 49: # Out of block range
                    self.factory.logger.info("Kicked '%s'; Tried to place an invalid block.; Block: '%s'" % (
                                            self.ip, block))
                    self.sendError("Invalid blocks are not allowed!")
                    return
                if block in [8, 10]: # Active Water and Lava
                    self.factory.logger.info("Kicked '%s'; Tried to place an invalid block.; Block: '%s'" % (
                                            self.ip, block))
                    self.sendError("Invalid blocks are not allowed!")
                    return
                if block == 7 and not self.isOp():
                    self.factory.logger.info("Kicked '%s'; Tried to place admincrete." % self.ip)
                    self.sendError("Don't build admincrete!")
                    return
                try:
                # If we're read-only, reverse the change
                    if self.isSpectator():
                        self.sendBlock(x, y, z)
                        self.sendServerMessage("Spectators cannot edit worlds.")
                        return
                    allowbuild = self.factory.runHook("onBlockClick", {"x": x, "y": y, "z": z, "block": block, "client": self})
                    if allowbuild is False:
                        self.sendBlock(x, y, z)
                        return
                    elif not self.allowedToBuild(x, y, z):
                        self.sendBlock(x, y, z)
                        return
                    # This tries to prevent out-of-range errors on the blockstore
                    # Track if we need to send back the block change
                    overridden = False
                    selected_block = block
                    # If we're deleting, block is actually air
                    # (note the selected block is still stored as selected_block)
                    if not created:
                        block = 0
                    # Pre-hook, for stuff like /paint
                    new_block = self.factory.runHook("preBlockChange", {"x": x, "y": y, "z": z, "block": block, "selected_block": selected_block, "client": self})
                    if new_block is not None:
                        block = new_block
                        overridden = True
                    # Block detection hook that does not accept any parameters
                    self.factory.runHook("blockDetect", {"x": x, "y": y, "z": z, "block": block, "client": self})
                    # Call hooks
                    new_block = self.factory.runHook("blockChange", {"x": x, "y": y, "z": z, "block": block, "selected_block": selected_block, "client": self})
                    if new_block is False:
                        # They weren't allowed to build here!
                        self.sendBlock(x, y, z)
                        continue
                    elif new_block == -1:
                        print "somebody else"
                        # Someone else handled building, just continue
                        continue
                    elif new_block is not None:
                        if new_block != True:
                            block = new_block
                            overridden = True
                    # OK, save the block
                    self.world[x, y, z] = chr(block)
                    # Now, send the custom block back if we need to
                    if overridden:
                        self.sendBlock(x, y, z, block)
                # Out of bounds!
                except (KeyError, AssertionError):
                    self.sendPacked(TYPE_BLOCKSET, x, y, z, "\0")
                # OK, replay changes to others
                else:
                    self.factory.queue.put((self, TASK_BLOCKSET, (x, y, z, block)))
                    if len(self.last_block_changes) >= 2:
                        self.last_block_changes = [(x, y, z)] + self.last_block_changes[:1] + self.last_block_changes[1:2]
                    else:
                        self.last_block_changes = [(x, y, z)] + self.last_block_changes[:1]
            elif type == TYPE_PLAYERPOS:
                # If we're loading a world, ignore these.
                if self.loading_world:
                    continue
                naff, x, y, z, h, p = parts
                pos_change = not (x == self.x and y == self.y and z == self.z)
                dir_change = not (h == self.h and p == self.p)
                if self.frozen:
                    newx, newy, newz = self.x >> 5, self.y >> 5, self.z >> 5
                    self.teleportTo(newx, newy, newz, h, p)
                    return
                override = self.factory.runHook("posChange", {"x": x, "y": y, "z": z, "h": h, "p": p, "client": self})
                # Only send changes if the hook didn't say no
                if override != False:
                    if pos_change:
                        # Send everything to the other clients
                        self.factory.queue.put(
                            (self, TASK_PLAYERPOS, (self.id, self.x, self.y, self.z, self.h, self.p)))
                    elif dir_change:
                        self.factory.queue.put((self, TASK_PLAYERDIR, (self.id, self.h, self.p)))
                self.x, self.y, self.z, self.h, self.p = x, y, z, h, p
            elif type == TYPE_MESSAGE:
                # We got a message.
                byte, message = parts
                override = self.factory.runHook("chatUsername", {"client": self})
                user = override if override else self.username
                override = self.factory.runHook("messageSent", {"client": self, "message": message})
                if self.identified == False:
                    self.factory.logger.info("Kicked '%s'; did not send a login before chatting; Message: '%s'" % (
                    self.ip, message))
                    self.sendError("Provide an authentication before chatting.")
                    return
                for c in message.lower():
                    if not c in PRINTABLE:
                        self.factory.logger.info("Kicked '%s'; Tried to use invalid characters; Message: '%s'" % (
                        self.ip, message))
                        self.sendError("Invalid characters are not allowed!")
                        return
                message = sanitizeMessage(message, [MSGREPLACE["text_colour_to_game"], MSGREPLACE["irc_colour_to_game"], MSGREPLACE["escape_commands"]])
                message = message.replace("%$rnd", "&$rnd")
                if message[len(message) - 2] == "&":
                    self.sendServerMessage("You cannot use a color at the end of a message")
                    return
                if len(message) > 51:
                    moddedmsg = message[:51].replace(" ", "")
                    if moddedmsg[len(moddedmsg) - 2] == "&":
                        message = message.replace("&", "*")
                time = datetime.datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S")
                if message.startswith("/"):
                    # It's a command
                    parts = [x.strip() for x in message.split() if x.strip()]
                    command = parts[0].strip("/")
                    if command.lower() in (self.factory.commands.keys() + self.factory.aliases.keys()):
                        self.factory.runCommand(command.strip("/").lower(), parts, "user", False, client=self)
                    else:
                        self.sendServerMessage("Command %s does not exist." % command)
                elif message.startswith("@"):
                    # It's a whisper
                    try:
                        username, text = message[1:].strip().split(" ", 1)
                    except ValueError:
                        self.sendServerMessage("Please include a username and a message to send.")
                    else:
                        if username.lower() in self.factory.usernames:
                            self.factory.usernames[username].sendWhisper(self.username, text)
                            self.sendWhisper(self.username, text)
                            self.factory.logger.info("%s to %s: %s" % (self.username, username, text))
                            self.factory.chatlogs["whisper"].write(
                                    {"self": self.username, "other": username, "text": text})
                            self.factory.chatlogs["main"].write({"self": self.username, "other": username, "text": text}
                                , formatter=MSGLOGFORMAT["whisper"])
                        else:
                            self.sendServerMessage("%s is currently offline." % username)
                elif message.startswith("!"):
                    # It's a world message.
                    if len(message) < 2:
                        self.sendServerMessage("Please include a message to send.")
                    else:
                        text = message[1:]
                        self.factory.sendMessageToAll(text, "world", self, fromloc="user")
                elif message.startswith("#"):
                    # It's a staff-only message.
                    if len(message) == 1:
                        if self.isMod():
                            self.sendServerMessage("Please include a message to send.")
                        else:
                            self.factory.sendMessageToAll(text, "chat", self, fromloc="user")
                    else:
                        text = message[1:]
                        self.factory.sendMessageToAll(text, "staff", self, fromloc="user")
                        self.factory.chatlogs["staff"].write({"time": time, "username": self.username, "text": text})
                        self.factory.chatlogs["main"].write({"time": time, "username": self.username, "text": text},
                            formatter=MSGLOGFORMAT["staff"])
                else:
                    if self.isSilenced():
                        self.sendServerMessage("You are silenced and cannot speak.")
                        return
                    if not override:
                        self.factory.sendMessageToAll(message, "chat", client=self, user=user, fromloc="user")
            else:
                if type == 2:
                    self.factory.logger.warn("Beta client attempted to connect.")
                    self.sendPacked(255, packString("Sorry, but this is a Classic-only server."))
                    self.transport.loseConnection()
                else:
                    self.factory.logger.warn("Unable to handle type %s" % type)

    def userColour(self):
        if self.factory.colors:
            if (self.username.lower() in self.factory.spectators):
                colour = RANK_COLOURS["spectator"]
            elif (self.username.lower() in self.factory.owners):
                colour = RANK_COLOURS["owner"]
            elif (self.username.lower() in self.factory.directors):
                colour = RANK_COLOURS["director"]
            elif (self.username.lower() in self.factory.admins):
                colour = RANK_COLOURS["admin"]
            elif (self.username.lower() in self.factory.mods):
                colour = RANK_COLOURS["mod"]
            elif (self.username.lower() in self.factory.helpers):
                colour = RANK_COLOURS["helper"]
            elif self.username.lower() in INFO_VIPLIST:
                colour = RANK_COLOURS["vip"]
            elif not hasattr(self, "world"):
                colour = RANK_COLOURS["default"]
            elif (self.username.lower() == self.world.status["owner"].lower()):
                colour = RANK_COLOURS["worldowner"]
            elif (self.username.lower() in self.world.ops):
                colour = RANK_COLOURS["op"]
            elif (self.username.lower() in self.world.builders):
                colour = RANK_COLOURS["builder"]
            else:
                colour = RANK_COLOURS["guest"]
        else:
            colour = RANK_COLOURS["default"]
        return colour

    def colouredUsername(self):
        return self.userColour() + self.username

    def teleportTo(self, x, y, z, h=0, p=0):
        "Teleports the client to the coordinates"
        if h > 255:
            h = 255
        self.sendPacked(TYPE_PLAYERPOS, 255, (x << 5) + 16, (y << 5) + 16, (z << 5) + 16, h, p)

    def changeToWorld(self, world_id, position=None):
        self.factory.queue.put((self, TASK_WORLDCHANGE, (self.id, self.world)))
        self.loading_world = True
        world = self.factory.joinWorld(world_id, self)
        self.factory.runHook("newWorld", {"client": self, "world": world})
        # These code should be plugin-fied, can anybody check?
        if not self.isOp():
            self.block_overrides = {}
        self.last_block_changes = []
        # End of code that needs to be plugin-fied
        self.initial_position = position
        if self.world.status["is_archive"]:
            self.sendSplitServerMessage(
                "This world is an archive, and will cease to exist once the last person leaves.")
            self.sendServerMessage(COLOUR_RED + "Staff: Please do not reboot this world.")
        if self.world.hidden:
            self.sendSplitServerMessage(COLOUR_GREEN + "This world is hidden, and does not show up on the world list.")
        if self.world.status["last_access_count"] > 0:
            self.world.status["last_access_count"] = 0
        breakable_admins = self.factory.runHook("canBreakAdmincrete", {"client": self})
        self.sendPacked(TYPE_INITIAL, 7, ("%s: %s" % (self.factory.server_name, world_id)),
            "Entering world '%s'" % world_id, 100 if breakable_admins else 0)
        self.sendLevel()

    def sendRankUpdate(self):
        "Sends a rank update."
        self.factory.runHook("rankChanged", {"client": self})
        self.respawn()

    def respawn(self):
        "Respawns the user in-place for other users, updating their nick."
        self.queueTask(TASK_PLAYERRESPAWN, [self.id, self.colouredUsername(), self.x, self.y, self.z, self.h, self.p])

    def sendBlock(self, x, y, z, block=None):
        try:
            def real_send(block):
                self.sendPacked(TYPE_BLOCKSET, x, y, z, block)

            if block is not None:
                real_send(block)
            else:
                self.world[x, y, z].addCallback(real_send)
        except AssertionError:
            self.factory.logger.warn("Block out of range: %s %s %s" % (x, y, z))

    def sendPlayerPos(self, id, x, y, z, h, p):
        self.sendPacked(TYPE_PLAYERPOS, id, x, y, z, h, p)

    def sendPlayerDir(self, id, h, p):
        self.sendPacked(TYPE_PLAYERDIR, id, h, p)

    def sendAdminBlockUpdate(self):
        "Sends a packet that updates the client's admin-building ability"
        self.sendPacked(TYPE_INITIAL, 6, ("%s: %s" % (self.factory.server_name, self.world.id)), "Reloading the server...", self.isOp() and 100 or 0)

    def sendMessage(self, id, colour, username, text, action=False):
        "Sends a message to the user, splitting it up if needed."
        # See if it's muted.
        replacement = self.factory.runHook("messageReceived", {"client": self, "colour": colour, "username": username, "text": text, "action": action})
        if replacement == False: return
        # See if we should highlight the names
        if action:
            prefix = "%s* %s%s%s " % (COLOUR_YELLOW, colour, username, COLOUR_WHITE)
        else:
            prefix = "%s%s:%s " % (colour, username, COLOUR_WHITE)
            # Send the message in more than one bit if needed
        self._sendMessage(prefix, text, id)

    def _sendMessage(self, prefix, message, id=127):
        "Utility function for sending messages, which does line splitting."
        lines = []
        temp = []
        thisline = ""
        words = message.split()
        linelen = 63 - len(prefix)
        for x in words:
            if len(thisline + " " + x) < linelen:
                thisline = thisline + " " + x
            else:
                if len(x) > linelen:
                    if not thisline == "":
                        lines.append(thisline)
                    while len(x) > linelen:
                        temp.append(x[:linelen])
                        x = x[linelen:]
                    lines = lines + temp
                    thisline = x
                else:
                    lines.append(thisline)
                    thisline = x
        if thisline != "":
            lines.append(thisline)
        for line in lines:
            if len(line) > 0:
                if line[0] == " ":
                    newline = line[1:]
                else:
                    newline = line
                if newline[len(newline) - 2] == "&":
                    newline = newline[:len(newline) - 2]
                self.sendPacked(TYPE_MESSAGE, id, prefix + newline)

    def sendAction(self, id, colour, username, text):
        self.sendMessage(id, colour, username, text, action=True)

    def sendWhisper(self, username, text):
        self.sendNormalMessage("%s@%s%s: %s%s" % (COLOUR_YELLOW, self.userColour(), username, COLOUR_WHITE, text))

    def sendServerMessage(self, message, user=None):
        self.sendPacked(TYPE_MESSAGE, 255, message)

    def sendNormalMessage(self, message):
        self._sendMessage("", message)

    def sendWorldMessage(self, message):
        "Sends a message to everyone in the current world."
        self.factory.sendMessageToAll(COLOUR_YELLOW + message, "world", self, fromloc="user")

    def sendPlainWorldMessage(self, message):
        "Sends a message to everyone in the current world, without any added color."
        self.factory.sendMessageToAll(message, "world", self, fromloc="user")

    def sendServerList(self, items, wrap_at=63, plain=False):
        "Sends the items as server messages, wrapping them correctly."
        current_line = items[0]
        for item in items[1:]:
            if len(current_line) + len(item) + 1 > wrap_at:
                if plain:
                    self.sendNormalMessage(current_line)
                else:
                    self.sendServerMessage(current_line)
                current_line = item
            else:
                current_line += " " + item
        if plain:
            self.sendNormalMessage(current_line)
        else:
            self.sendServerMessage(current_line)

    def sendSplitServerMessage(self, message, plain=False):
        linelen = 63
        lines = []
        thisline = ""
        words = message.split()
        for x in words:
            if len(thisline + " " + x) < linelen:
                thisline = thisline + " " + x
            else:
                lines.append(thisline)
                thisline = x
        if thisline != "":
            lines.append(thisline)
        for line in lines:
            if plain:
                self.sendNormalMessage(line)
            else:
                self.sendNormalMessage(line)

    def sendNewPlayer(self, id, username, x, y, z, h, p):
        self.sendPacked(TYPE_SPAWNPOINT, id, username, x, y, z, h, p)

    def sendPlayerLeave(self, id):
        self.sendPacked(TYPE_PLAYERLEAVE, id)

    def sendKeepAlive(self):
        if self.connected:
            self.sendPacked(TYPE_KEEPALIVE)
            reactor.callLater(1, self.sendKeepAlive)

    def sendOverload(self):
        "Sends an overload - a fake world designed to use as much memory as it can."
        self.sendPacked(TYPE_INITIAL, 7, "Loading...", "Entering world 'default'...", 0)
        self.sendPacked(TYPE_PRECHUNK)
        reactor.callLater(0.001, self.sendOverloadChunk)

    def sendOverloadChunk(self):
        "Sends a level chunk full of 1s."
        if self.connected:
            self.sendPacked(TYPE_CHUNK, 1024, "\1" * 1024, 50)
            reactor.callLater(0.001, self.sendOverloadChunk)

    def sendLevel(self):
        "Starts the process of sending a level to the client."
        self.factory.recordPresence(self.username)
        # Ask the World to flush the level and get a gzip handle back to us.
        if hasattr(self, "world"):
            self.world.get_gzip_handle().addCallback(self.sendLevelStart)

    def sendLevelStart(self, (gzip_handle, zipped_size)):
        "Called when the world is flushed and the gzip is ready to read."
        # Store that handle and size
        self.zipped_level, self.zipped_size = gzip_handle, zipped_size
        # Preload our first chunk, send a level stream header, and go!
        self.chunk = self.zipped_level.read(1024)
        self.factory.logger.debug("Sending level...")
        self.sendPacked(TYPE_PRECHUNK)
        reactor.callLater(0.001, self.sendLevelChunk)

    def sendLevelChunk(self):
        if not hasattr(self, 'chunk'):
            self.factory.logger.error("Cannot send chunk, there isn't one! %r %r" % (self, self.__dict__))
            return
        if self.chunk:
            self.sendPacked(TYPE_CHUNK, len(self.chunk), self.chunk,
                chr(int(100 * (self.zipped_level.tell() / float(self.zipped_size)))))
            self.chunk = self.zipped_level.read(1024)
            reactor.callLater(0.001, self.sendLevelChunk)
        else:
            self.zipped_level.close()
            del self.zipped_level
            del self.chunk
            del self.zipped_size
            self.endSendLevel()

    def endSendLevel(self):
        self.factory.logger.debug("Sent level data.")
        self.sendPacked(TYPE_LEVELSIZE, self.world.x, self.world.y, self.world.z)
        sx, sy, sz, sh = self.world.spawn
        self.p = 0
        self.loading_world = False
        # If we have a custom point set (teleport, tp), use that
        if self.initial_position:
            try:
                sx, sy, sz, sh = self.initial_position
            except ValueError:
                sx, sy, sz = self.initial_position
                sh = 0
            self.initial_position = None
        self.x, self.y, self.z, self.h = (sx << 5) + 16, (sy << 5) + 16, (sz << 5) + 16, int(sh * 255 / 360.0)
        self.sendPacked(TYPE_SPAWNPOINT, chr(255), "", self.x, self.y, self.z, self.h, 0)
        self.sendAllNew()
        self.factory.queue.put((self, TASK_NEWPLAYER, (self.id, self.colouredUsername(), self.x, self.y, self.z, self.h, 0)))
        self.sendWelcome()

    def sendAllNew(self):
        "Sends a 'new user' notification for each new user in the world."
        for client in self.world.clients:
            if client is not self and hasattr(client, "x"):
                self.sendNewPlayer(client.id, client.userColour() + client.username, client.x, client.y, client.z,
                    client.h, client.p)

    def sendWelcome(self):
        if not self.sent_first_welcome:
            for line in self.factory.greeting:
                self.sendPacked(TYPE_MESSAGE, 127, line)
            self.sent_first_welcome = True
        else:
            self.sendPacked(TYPE_MESSAGE, 255, "You are now in world '%s'" % self.world.id)

    def allowedToBuild(self, x, y, z):
        build = False
        assigned = []
        try:
            check_offset = self.world.blockstore.get_offset(x, y, z)
            block = ord(self.world.blockstore.raw_blocks[check_offset])
        except:
            self.sendServerMessage("Out of bounds.")
            return False
        if block == BLOCK_SOLID and not self.isOp():
            return False
        for id, zone in self.world.userzones.items():
            x1, y1, z1, x2, y2, z2 = zone[1:7]
            if x1 < x < x2:
                if y1 < y < y2:
                    if z1 < z < z2:
                        if len(zone) > 7:
                            if self.username.lower() in zone[7:] or self.isDirector():
                                build = True
                            else:
                                assigned = zone[7:]
                        else:
                            return False
        if build:
            return True
        elif assigned:
            self.sendSplitServerMessage("You are not allowed to build in this zone. Only: %s may." % ", ".join(assigned))
            return False
        for id, zone in self.world.rankzones.items():
            if zone[7] == "all":
                x1, y1, z1, x2, y2, z2 = zone[1:7]
                if x1 < x < x2:
                    if y1 < y < y2:
                        if z1 < z < z2:
                            return True
            if self.world.status["zoned"]:
                for rank in ["Builder", "Op", "WorldOwner", "Mod", "Admin", "Director", "Owner"]:
                    # TODO: Implement a rank checking system that doesn't suck.
                    rankFunc = getattr(self, "is%s" % rank)()
                    if zone[7] == rank.lower():
                        x1, y1, z1, x2, y2, z2 = zone[1:7]
                        if x1 < x < x2:
                            if y1 < y < y2:
                                if z1 < z < z2:
                                    if rankFunc():
                                        return True
                                    else:
                                        self.sendServerMessage("You must be %s %s to build here." % (("an" if rank[0] in "aeiou" else "a"), rank.lower()))
                                        return False
        if self.world.id == self.factory.default_name and not self.isMod() and not self.world.status["all_build"]:
            self.sendBlock(x, y, z)
            self.sendServerMessage("Only Builder/Op and Mod+ may edit '%s'." % self.factory.default_name)
            return
        if not self.world.status["all_build"] and self.isBuilder() or self.isOp():
            return True
        if self.world.status["all_build"]:
            return True
        self.sendServerMessage("This world is locked. You must be Builder/Op or Mod+ to build here.")
        return False

    def getBlockValue(self, value):
        # Try getting the block as a direct integer type.
        try:
            block = chr(int(value))
        except ValueError:
            # OK, try a symbolic type.
            try:
                block = chr(globals()['BLOCK_%s' % value.upper()])
            except KeyError:
                self.sendServerMessage("'%s' is not a valid block type." % value)
                return None
        # Check the block is valid
        if ord(block) > 49:
            self.sendServerMessage("'%s' is not a valid block type." % value)
            return None
        op_blocks = [BLOCK_SOLID, BLOCK_WATER, BLOCK_LAVA]
        if ord(block) in op_blocks and not self.isOp():
            self.sendServerMessage("Sorry, but you can't use that block.")
            return
        return block

    def canBreakAdminBlocks(self):
        "Shortcut for checking permissions."
        if not hasattr(self, "world"):
            return False
        return self.isOp()

    def getBlbLimit(self, factor=1):
        """Fetches BLB Limit, and returns limit multiplied by a factor. 0 is returned if blb is disabled for that usergroup, and -1 for no limit."""
        if self.factory.useblblimit:
            if self.isSpectator():
                limit = 0
            for rank in ["Owner", "Director", "Admin", "Mod", "Helper", "WorldOwner", "Op", "Builder"]:
                # TODO: Implement a rank checking system that doesn't suck.
                if getattr(data["client"], "is%s" % rank)():
                    limit = self.factory.blblimit[rank.lower()]
                    break
        else:
            if self.isSpectator():
                limit = 0
            elif self.isOwner():
                limit = -1
            elif self.isDirector():
                limit = 8796093022208
            elif self.isAdmin():
                limit = 2199023255552
            elif self.isMod():
                limit = 2097152
            elif self.isHelper():
                limit = 262144
            elif self.isWorldOwner():
                limit = 176128
            elif self.isOp():
                limit = 110592
            elif self.isBuilder():
                limit = 8124
            else:
                limit = 128
        if limit > -1:
            limit *= factor
        return limit