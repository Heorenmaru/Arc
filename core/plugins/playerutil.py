import cmath, cPickle

from core.constants import *
from core.decorators import *
from core.globals import *
from core.plugins import ProtocolPlugin
from core.timer import ResettableTimer

class PlayerUtilPlugin(ProtocolPlugin):

    commands = {
        "say": "commandSay",
        "msg": "commandSay",
        "me": "commandMe",
        "away": "commandAway",
        "afk": "commandAway",
        "brb": "commandAway",
        "back": "commandBack",
        "slap": "commandSlap",
        "kill": "commandKill",
        "smack": "commandSmack",
        "roll": "commandRoll",

        "rank": "commandRank",
        "setrank": "commandRank",
        "derank": "commandDeRank",
        "spec": "commandSpec",
        "unspec": "commandDeSpec",
        "despec": "commandDeSpec",
        "specced": "commandSpecced",
        "writer": "commandOldRanks",
        "builder": "commandOldRanks",
        "op": "commandOldRanks",
        "helper": "commandOldRanks",
        "mod": "commandOldRanks",
        "admin": "commandOldRanks",
        "director": "commandOldRanks",
        "dewriter": "commandOldDeRanks",
        "debuilder": "commandOldDeRanks",
        "deop": "commandOldDeRanks",
        "dehelper": "commandOldDeRanks",
        "demod": "commandOldDeRanks",
        "deadmin": "commandOldDeRanks",
        "dedirector": "commandOldDeRanks",

        "respawn": "commandRespawn",

        "fetch": "commandFetch",
        "bring": "commandFetch",
        "invite": "commandInvite",

        "rainbow": "commandRainbow",
        "fabulous": "commandRainbow",
        "fab": "commandRainbow",
        "mefab": "commandMeRainbow",
        "merainbow": "commandMeRainbow",

        "fly": "commandFly",

        "coord": "commandCoord",
        "goto": "commandCoord",
        "tp": "commandTeleport",
        "teleport": "commandTeleport",

        "who": "commandWho",
        "whois": "commandWho",
        "players": "commandWho",
        "pinfo": "commandWho",
        "locate": "commandLocate",
        "find": "commandLocate",
        "lastseen": "commandLastseen",

        "count": "commandCount",
        "countdown": "commandCount",

        "mute": "commandMute",
        "unmute": "commandUnmute",
        "muted": "commandMuted",
        }

    hooks = {
        "chatmsg": "message",
        "poschange": "posChanged",
        "newworld": "newWorld",
        "recvmessage": "messageReceived",
    }

    colors = ["&4", "&c", "&e", "&a", "&2", "&3", "&b", "&d", "&5"]

    def loadRank(self):
        file = open('config/data/titles.dat', 'r')
        rank_dic = cPickle.load(file)
        file.close()
        return rank_dic

    def dumpRank(self, bank_dic):
        file = open('config/data/titles.dat', 'w')
        cPickle.dump(bank_dic, file)
        file.close()

    def gotClient(self):
        self.client.var_fetchrequest = False
        self.client.var_fetchdata = ()
        self.flying = False
        self.last_flying_block = None
        self.num = int(0)
        self.muted = set()

    def message(self, message):
        if self.client.var_fetchrequest:
            self.client.var_fetchrequest = False
            if message in ["y", "yes"]:
                sender, world, rx, ry, rz = self.client.var_fetchdata
                if self.client.world == world:
                    self.client.teleportTo(rx, ry, rz)
                else:
                    self.client.changeToWorld(world.id, position=(rx, ry, rz))
                self.client.sendServerMessage("You have accepted the fetch request.")
                sender.sendServerMessage("%s has accepted your fetch request." % self.client.username)
            elif message in ["n", "no"]:
                sender = self.client.var_fetchdata[0]
                self.client.sendServerMessage("You did not accept the fetch request.")
                sender.sendServerMessage("%s did not accept your request." % self.client.username)
            else:
                sender = self.client.var_fetchdata[0]
                self.client.sendServerMessage("You have ignored the fetch request.")
                sender.sendServerMessage("%s has ignored your request." % self.client.username)
                return
            return True

    def messageReceived(self, colour, username, text, action):
        "Stop viewing a message if we've muted them."
        if username.lower() in self.muted:
            return False

    def posChanged(self, x, y, z, h, p):
        "Hook trigger for when the user moves"
        # Are we fake-flying them?
        if self.flying:
            fly_block_loc = ((x>>5),((y-48)>>5)-1,(z>>5))
            if not self.last_flying_block:
                # OK, send the first flying blocks
                self.setCsBlock(fly_block_loc[0], fly_block_loc[1], fly_block_loc[2], BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0], fly_block_loc[1] - 1, fly_block_loc[2], BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0] - 1, fly_block_loc[1], fly_block_loc[2], BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0] + 1, fly_block_loc[1], fly_block_loc[2], BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0], fly_block_loc[1], fly_block_loc[2] - 1, BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0], fly_block_loc[1], fly_block_loc[2] + 1, BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0] - 1, fly_block_loc[1], fly_block_loc[2] - 1, BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0] - 1, fly_block_loc[1], fly_block_loc[2] + 1, BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0] + 1, fly_block_loc[1], fly_block_loc[2] - 1, BLOCK_GLASS)
                self.setCsBlock(fly_block_loc[0] + 1, fly_block_loc[1], fly_block_loc[2] + 1, BLOCK_GLASS)
            else:
                # Have we moved at all?
                if fly_block_loc != self.last_flying_block:
                    self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1] - 1, self.last_flying_block[2], BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1], self.last_flying_block[2], BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0] - 1, self.last_flying_block[1], self.last_flying_block[2], BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0] + 1, self.last_flying_block[1], self.last_flying_block[2], BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1], self.last_flying_block[2] - 1, BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1], self.last_flying_block[2] + 1, BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0] - 1, self.last_flying_block[1], self.last_flying_block[2] - 1, BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0] - 1, self.last_flying_block[1], self.last_flying_block[2] + 1, BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0] + 1, self.last_flying_block[1], self.last_flying_block[2] - 1, BLOCK_AIR)
                    self.setCsBlock(self.last_flying_block[0] + 1, self.last_flying_block[1], self.last_flying_block[2] + 1, BLOCK_AIR)
                    self.setCsBlock(fly_block_loc[0], fly_block_loc[1], fly_block_loc[2], BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0], fly_block_loc[1] - 1, fly_block_loc[2], BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0] - 1, fly_block_loc[1], fly_block_loc[2], BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0] + 1, fly_block_loc[1], fly_block_loc[2], BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0], fly_block_loc[1], fly_block_loc[2] - 1, BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0], fly_block_loc[1], fly_block_loc[2] + 1, BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0] - 1, fly_block_loc[1], fly_block_loc[2] - 1, BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0] - 1, fly_block_loc[1], fly_block_loc[2] + 1, BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0] + 1, fly_block_loc[1], fly_block_loc[2] - 1, BLOCK_GLASS)
                    self.setCsBlock(fly_block_loc[0] + 1, fly_block_loc[1], fly_block_loc[2] + 1, BLOCK_GLASS)
            self.last_flying_block = fly_block_loc
        else:
            if self.last_flying_block:
                self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1], self.last_flying_block[2], BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1] - 1, self.last_flying_block[2], BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0] - 1, self.last_flying_block[1], self.last_flying_block[2], BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0] + 1, self.last_flying_block[1], self.last_flying_block[2], BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1], self.last_flying_block[2] - 1, BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0], self.last_flying_block[1], self.last_flying_block[2] + 1, BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0] - 1, self.last_flying_block[1], self.last_flying_block[2] - 1, BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0] - 1, self.last_flying_block[1], self.last_flying_block[2] + 1, BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0] + 1, self.last_flying_block[1], self.last_flying_block[2] - 1, BLOCK_AIR)
                self.setCsBlock(self.last_flying_block[0] + 1, self.last_flying_block[1], self.last_flying_block[2] + 1, BLOCK_AIR)
                self.last_flying_block = None

    def newWorld(self, world):
        "Hook to reset flying abilities in new worlds if not op."
        if self.client.isSpectator():
            self.flying = False

    def setCsBlock(self, x, y, z, type):
        if y > -1 and x > -1 and z > -1:
            if y < self.client.world.y and x < self.client.world.x and z < self.client.world.z:
                if ord(self.client.world.blockstore.raw_blocks[self.client.world.blockstore.get_offset(x, y, z)]) is 0:
                    self.client.sendPacked(TYPE_BLOCKSET, x, y, z, type)

    def sendgo(self):
        self.client.sendPlainWorldMessage("&7GET SET: &aGO!")
        self.num = 0

    def sendcount(self, count):
        if int(self.num)-int(count) == 1:
            self.client.sendPlainWorldMessage("&7GET READY: &e1")
        elif not int(self.num)-int(count) == 0:
            self.client.sendPlainWorldMessage("&7COUNTDOWN: &c%s" %(int(self.num)-int(count)))

    @config("category", "player")
    def commandBack(self, parts, fromloc, overriderank):
        "/back - Guest\nPrints out message of you coming back."
        if fromloc == "user":
            if len(parts) != 1:
                self.client.sendServerMessage("This command doesn't need arguments")
            else:
                if self.client.isSilenced():
                    self.client.sendServerMessage("Cat got your tongue?")
                else:
                    self.client.factory.queue.put((self.client, TASK_AWAYMESSAGE, self.client.username + " is now: Back."))
                self.client.gone = 0
                self.client.resetIdleTimer()

    @config("category", "player")
    def commandAway(self, parts, fromloc, overriderank):
        "/away reason - Guest\nAliases: afk, brb\nPrints out message of you going away."
        if fromloc == "user":
            if len(parts) == 1:
                if self.client.isSilenced():
                    self.client.sendServerMessage("Cat got your tongue?")
                else:
                    self.client.factory.queue.put((self.client, TASK_AWAYMESSAGE, self.client.username + " has gone: Away."))
            else:
                if self.client.isSilenced():
                    self.client.sendServerMessage("Cat got your tongue?")
                else:
                    self.client.factory.queue.put((self.client, TASK_AWAYMESSAGE, self.client.username + " has gone: Away "+(" ".join(parts[1:]))))
            self.client.gone = 1
            self.client.resetIdleTimer()

    @config("category", "player")
    def commandMe(self, parts, fromloc, overriderank):
        "/me action - Guest\nPrints 'username action'"
        if fromloc == "user":
            if len(parts) == 1:
                self.client.sendServerMessage("Please type an action.")
            else:
                if self.client.isSilenced():
                    self.client.sendServerMessage("Cat got your tongue?")
                else:
                    self.client.factory.queue.put((self.client, TASK_ACTION, (self.client.id, self.client.userColour(), self.client.username, " ".join(parts[1:]))))

    @config("rank", "mod")
    def commandSay(self, parts, fromloc, overriderank):
        "/say message - Mod\nAliases: msg\nPrints out message in the server color."
        if len(parts) == 1:
            self.client.sendServerMessage("Please type a message.")
        else:
            self.client.factory.queue.put((self.client, TASK_SERVERMESSAGE, ("02[MSG] "+(" ".join(parts[1:])))))

    @config("category", "player")
    def commandSlap(self, parts, fromloc, overriderank):
        "/slap username [with object] - Guest\nSlap username [with object]."
        if len(parts) == 1:
            self.client.sendServerMessage("Enter the name for the slappee")
        else:
            stage = 0
            name = ''
            object = ''
        for i in range(1, len(parts)):
            if parts[i] == "with":
                stage = 1
                continue
            if stage == 0 :
                name += parts[i]
                if (i+1 != len(parts) ) :
                    if ( parts[i+1] != "with" ) : name += " "
            else:
                object += parts[i]
                if ( i != len(parts) - 1 ) : object += " "
        else:
            if stage == 1:
                self.client.sendWorldMessage("* "+COLOUR_PURPLE+"%s slapped %s with %s!" % (self.client.username, name, object))
                if self.client.factory.irc_relay:
                    self.client.factory.irc_relay.sendServerMessage("%s slapped %s with %s!" % (self.client.username, name, object))
            else:
                self.client.sendWorldMessage("* "+COLOUR_PURPLE+"%s slapped %s with a giant smelly trout!" % (self.client.username, name))
                if self.client.factory.irc_relay:
                    self.client.factory.irc_relay.sendServerMessage("* %s slapped %s with a giant smelly trout!" % (self.client.username, name))

    @config("rank", "mod")
    @username_command
    def commandKill(self, user, fromloc, overriderank, params=[]):
        "/kill username [reason] - Mod\nKills the user for reason (optional)"
        killer = self.client.username
        if user.isMod():
            self.client.sendServerMessgae("You can't kill staff!")
        else:
            user.teleportTo(user.world.spawn[0], user.world.spawn[1], user.world.spawn[2], user.world.spawn[3])
            user.sendServerMessage("You have been killed by %s." % self.client.username)
            self.client.factory.queue.put((self.client, TASK_SERVERURGENTMESSAGE, "%s has been killed by %s." % (user.username, killer)))
            if params:
                self.client.factory.queue.put((self.client, TASK_SERVERURGENTMESSAGE, "Reason: %s" % (" ".join(params))))

    @config("rank", "mod")
    @only_username_command
    def commandSmack(self, username, fromloc, overriderank, params=[]):
        "/smack username [reason] - Mod\Smacks the user for reason (optional)"
        smacker = self.client.username
        if user.isMod():
            self.client.sendServerMessgae("You can't smack staff!")
        else:
            if user.world == "default":
                user.teleportTo(self.factory.worlds["default"].spawn[0], self.factory.worlds["default"].spawn[1], self.factory.worlds["default"].spawn[2])
            else:
                user.changeToWorld("default")
            user.sendServerMessage("You have been smacked by %s." % self.client.username)
            self.client.factory.queue.put((self.client, TASK_SERVERURGENTMESSAGE, "%s has been smacked by %s." % (user.username, smacker)))
            if params:
                self.client.factory.queue.put((self.client, TASK_SERVERURGENTMESSAGE, "Reason: %s" % (" ".join(params))))

    def commandRoll(self, parts, fromloc, overriderank):
        "/roll max - Guest\nRolls a random number from 1 to max. Announces to world."
        if len(parts) == 1:
            self.client.sendServerMessage("Please enter a number as the maximum roll.")
        else:
            try:
                roll = int(cmath.floor((random.random()*(int(parts[1]) - 1) + 1)))
            except ValueError:
                self.client.sendServerMessage("Please enter an integer as the maximum roll.")
            else:
                self.client.sendWorldMessage("%s rolled a %s" % (self.client.username, roll))

    @config("category", "player")
    @config("rank", "mod")
    def commandSpecced(self, user, fromloc, overriderank):
        "/specced - Mod\nShows who is Specced."
        if len(self.client.factory.spectators):
            self.client.sendServerList(["Specced:"] + list(self.client.factory.spectators))
        else:
            self.client.sendServerList(["Specced: No one."])

    @config("category", "player")
    @config("rank", "op")
    def commandRank(self, parts, fromloc, overriderank):
        "/rank rankname username - Op\nAliases: setrank\nMakes username the rank of rankname."
        if len(parts) < 3:
            self.client.sendServerMessage("You must specify a rank and username.")
        else:
            self.client.sendServerMessage(Rank(self, parts, fromloc, overriderank))

    @config("category", "player")
    @config("rank", "op")
    def commandDeRank(self, parts, fromloc, overriderank):
        "/derank rankname username - Op\nMakes username lose the rank of rankname."
        if len(parts) < 3:
            self.client.sendServerMessage("You must specify a rank and username.")
        else:
            self.client.sendServerMessage(DeRank(self, parts, fromloc, overriderank))

    @config("category", "player")
    @config("rank", "op")
    def commandOldRanks(self, parts, fromloc, overriderank):
        "/rankname username [world] - Op\nAliases: writer, builder, op, helper, mod, admin, director\nThis is here for Myne users."
        if len(parts) < 2:
            self.client.sendServerMessage("You must specify a rank and username.")
        else:
            if parts[0] == "/writer":
                parts[0] = "/builder"
            parts = ["/rank", parts[0][1:]] + parts[1:]
            self.client.sendServerMessage(Rank(self, parts, fromloc, overriderank))

    @config("category", "player")
    @config("rank", "op")
    def commandOldDeRanks(self, parts, fromloc, overriderank):
        "/derankname username [world] - Op\nAliases: dewriter, debuilder, deop, dehelper, demod, deadmin, dedirector\nThis is here for Myne users."
        if len(parts) < 2:
            self.client.sendServerMessage("You must specify a rank and username.")
        else:
            if parts[0] == "/dewriter":
                rank = "/debuilder"
            else:
                rank = parts[0]
            rank = rank.strip("/de")
            partsToSend = ["/derank", rank] + parts[1:]
            self.client.sendServerMessage(DeRank(self, partsToSend, fromloc, overriderank))

    @config("category", "player")
    @config("rank", "mod")
    @only_username_command
    def commandSpec(self, username, fromloc, overriderank):
        "/spec username - Mod\nMakes the user as a spec."
        self.client.sendServerMessage(Spec(self, username, fromloc, overriderank))

    @config("category", "player")
    @config("rank", "mod")
    @only_username_command
    def commandDeSpec(self, username, fromloc, overriderank):
        "/unspec username - Mod\nAliases: despec\nRemoves the user as a spec."
        self.client.sendServerMessage(DeSpec(self, username, fromloc, overriderank))

    @config("category", "player")
    @config("rank", "op")
    @username_command
    def commandRespawn(self, user, fromloc, overriderank):
        "/respawn username - Mod\nRespawns the user."
        if not self.isMod() and (user.world.id != self.client.world.id):
            self.client.sendServerMessage("The user is not in your world.")
        else:
            user.respawn()
            user.sendServerMessage("You have been respawned by %s." % self.client.username)
            self.client.sendServerMessage("%s respawned." % user.username)

    @config("disabled", True)
    def commandRainbow(self, parts, fromloc, overriderank):
        "/rainbow - Guest\nAliases: fabulous, fab\nMakes your text rainbow."
        if len(parts) == 1:
            self.client.sendServerMessage("Please include a message to rainbowify.")
        else:
            stringInput = parts[1:]
            input  = ""
            for a in stringInput:
                input = input + a + " "
            output = ""
            colorNum = 0
            for x in input:
                if x != " ":
                    output = output + self.colors[colorNum] + x
                    colorNum = colorNum + 1
                    if colorNum >= 9:
                        colorNum = 0
                if x == " ":
                    output = output + x
            self.client.factory.queue.put((self.client, TASK_ONMESSAGE, " "+self.client.userColour()+self.client.username+": "+output))

    @config("disabled", True)
    def commandMeRainbow(self, parts, fromloc, overriderank):
        "/mefab - Guest\nAliases: merainbow\nSends an action in rainbow colors."
        if len(parts) == 1:
            self.client.sendServerMessage("Please include an action to rainbowify.")
        else:
            stringInput = parts[1:]
            input  = ""
            for a in stringInput:
                input = input + a + " "
            output = ""
            colorNum = 0
            for x in input:
                if x != " ":
                    output = output + colors[colorNum] + x
                    colorNum = colorNum + 1
                    if colorNum >= 9:
                        colorNum = 0
                if x == " ":
                    output = output + x
            self.client.factory.queue.put((self.client, TASK_ONMESSAGE, "* "+self.client.userColour()+self.client.username+": "+output))

    @config("category", "player")
    @username_command
    def commandInvite(self, user, fromloc, overriderank):
        "/invite username - Guest\Invites a user to be where you are."
        # Shift the locations right to make them into block coords
        rx = self.client.x >> 5
        ry = self.client.y >> 5
        rz = self.client.z >> 5
        user.var_prefetchdata = (self.client, self.client.world)
        if self.client.world.id == user.world.id:
            user.sendServerMessage("%s would like to fetch you." % self.client.username)
        else:
            user.sendServerMessage("%s would like to fetch you to %s." % (self.client.username, self.client.world.id))
        user.sendServerMessage("Do you wish to accept? [y]es [n]o")
        user.var_fetchrequest = True
        user.var_fetchdata = (self.client, self.client.world, rx, ry, rz)
        self.client.sendServerMessage("The fetch request has been sent.")

    @config("category", "player")
    @config("rank", "op")
    @username_command
    def commandFetch(self, user, fromloc, overriderank):
        "/fetch username - Op\nAliases: bring\nTeleports a user to be where you are"
        # Shift the locations right to make them into block coords
        rx = self.client.x >> 5
        ry = self.client.y >> 5
        rz = self.client.z >> 5
        if user.world == self.client.world:
            user.teleportTo(rx, ry, rz)
        else:
            if self.client.isMod():
                user.changeToWorld(self.client.world.id, position=(rx, ry, rz))
            else:
                self.client.sendServerMessage("%s cannot be fetched from '%s'" % (self.client.username, user.world.id))
                return
        user.sendServerMessage("You have been fetched by %s" % self.client.username)

    @config("category", "player")
    @on_off_command
    def commandFly(self, onoff, fromloc, overriderank):
        "/fly on|off - Guest\nEnables or disables bad server-side flying"
        if onoff == "on":
            self.flying = True
            self.client.sendServerMessage("You are now flying.")
        else:
            self.flying = False
            self.client.sendServerMessage("You are no longer flying.")

    @config("category", "world")
    def commandCoord(self, parts, fromloc, overriderank):
        "/goto x y z [h p] - Guest\nTeleports you to coords. NOTE: y is up."
        try:
            x = int(parts[1])
            y = int(parts[2])
            z = int(parts[3])
            try:
                try:
                    h = int(parts[4])
                    self.client.teleportTo(x, y, z, h)
                except:
                    p = int(parts[5])
                    self.client.teleportTo(x, y, z, h, p)
            except:
                self.client.teleportTo(x, y, z)
        except (IndexError, ValueError):
            self.client.sendServerMessage("Usage: /goto x y z [h p]")
            self.client.sendServerMessage("MCLawl users: /l world name")
    
    @config("category", "player")
    @username_command
    def commandTeleport(self, user, fromloc, overriderank):
        "/tp username - Guest\nAliases: teleport\nTeleports you to the users location."
        x = user.x >> 5
        y = user.y >> 5
        z = user.z >> 5
        if user.world == self.client.world:
            self.client.teleportTo(x, y, z)
        else:
            if self.client.canEnter(user.world):
                self.client.changeToWorld(user.world.id, position=(x, y, z))
            else:
                self.client.sendServerMessage("Sorry, that world is private.")

    @only_username_command
    def commandLastseen(self, username, fromloc, overriderank):
        "/lastseen username - Guest\nTells you when 'username' was last seen."
        if username not in self.client.factory.lastseen:
            self.client.sendServerMessage("There are no records of %s." % username)
        else:
            t = time.time() - self.client.factory.lastseen[username]
            days = t // 86400
            hours = (t % 86400) // 3600
            mins = (t % 3600) // 60
            desc = "%id, %ih, %im" % (days, hours, mins)
            self.client.sendServerMessage("%s was last seen %s ago." % (username, desc))

    @username_command
    def commandLocate(self, user, fromloc, overriderank):
        "/locate username - Guest\nAliases: find\nTells you what world a user is in."
        self.client.sendServerMessage("%s is in %s" % (user.username, user.world.id))

    @config("category", "player")
    def commandWho(self, parts, fromloc, overriderank):
        "/who [username] - Guest\nAliases: pinfo, users, whois\nOnline users, or user lookup."
        if len(parts) < 2:
            self.client.sendServerMessage("Do '/who username' for more info.")
            userlist = set()
            for user in self.client.factory.usernames:
                if user is None:
                    pass # To avoid NoneType error
                else:
                    if user in self.client.factory.spectators:
                        user = COLOUR_BLACK + user
                    elif user in self.client.factory.owners:
                        user = COLOUR_DARKGREEN + user
                    elif user in self.client.factory.directors:
                        user = COLOUR_GREEN + user
                    elif user in self.client.factory.admins:
                        user = COLOUR_RED + user
                    elif user in self.client.factory.mods:
                        user = COLOUR_BLUE + user
                    elif user in self.client.factory.mods:
                        user = COLOUR_DARKBLUE + user
                    elif user is self.client.world.owner:
                        user = COLOUR_DARKYELLOW + user
                    elif user in self.client.world.ops:
                        user = COLOUR_DARKCYAN + user
                    elif user in self.client.world.builders:
                        user = COLOUR_CYAN + user
                    else:
                        user = COLOUR_WHITE + user
                userlist.add(user)
            self.client.sendServerList((["Players:"] + list(userlist)), plain=True)
        else:
            def loadBank():
                file = open('config/data/balances.dat', 'r')
                bank_dic = cPickle.load(file)
                file.close()
                return bank_dic
            def loadRank():
                file = open('config/data/titles.dat', 'r')
                rank_dic = cPickle.load(file)
                file.close()
                return rank_dic
            bank = loadBank()
            rank = loadRank()
            user = parts[1].lower()
            try:
                title = self.client.factory.usernames[user].title
            except:
                title = ""
            if parts[1].lower() in self.client.factory.usernames:
                # Parts is an array, always, so we get the first item.
                username = self.client.factory.usernames[parts[1].lower()]
                if self.client.isAdmin() or username.username.lower() == self.client.username.lower():
                    self.client.sendNormalMessage(self.client.factory.usernames[user].userColour()+("%s" % (title))+parts[1]+COLOUR_YELLOW+" "+username.world.id+" | "+str(username.transport.getPeer().host))
                else:
                    self.client.sendNormalMessage(self.client.factory.usernames[user].userColour()+("%s" % (title))+parts[1]+COLOUR_YELLOW+" "+username.world.id)
                if user in INFO_VIPLIST:
                    self.client.sendServerMessage("is an iCraft Developer")
                if username.gone == 1:
                    self.client.sendNormalMessage(COLOUR_DARKPURPLE+"is currently Away")
                if user in bank:
                    self.client.sendServerMessage("Balance: M%d" % (bank[user]))
            else:
                # Parts is an array, always, so we get the first item.
                username = parts[1].lower()
                self.client.sendNormalMessage(self.client.userColour()+("%s" % (title))+parts[1]+COLOUR_DARKRED+" Offline")
                try:
                    t = time.time() - self.client.factory.lastseen[username]
                except:
                    return
                days = t // 86400
                hours = (t % 86400) // 3600
                mins = (t % 3600) // 60
                desc = "%id, %ih, %im" % (days, hours, mins)
                if username in self.client.factory.lastseen:
                    self.client.sendServerMessage("On %s ago" % desc)
                if user in bank:
                    self.client.sendServerMessage("Balance: M%s" % bank[user])

    @config("rank", "op")
    def commandCount(self, parts, fromloc, overriderank):
        "/count [number] - Op\nAliases: countdown\nCounts down from 3 or from number given (up to 15)"
        if self.num != 0:
            self.client.sendServerMessage("You can only have one count at a time!")
            return
        if len(parts) > 1:
            try:
                self.num = int(parts[1])
            except ValueError:
                self.client.sendServerMessage("Number must be an integer!")
                return
        else:
            self.num = 3
        if self.num > 15:
            self.client.sendServerMessage("You can't count from higher than 15!")
            self.num = 0
            return
        counttimer = ResettableTimer(self.num, 1, self.sendgo, self.sendcount)
        self.client.sendPlainWorldMessage("&7COUNTDOWN: &c%s" %self.num)
        counttimer.start()

    @config("category", "player")
    @only_username_command
    def commandMute(self, username, fromloc, overriderank):
        "/mute username - Guest\nStops you hearing messages from 'username'."
        self.muted.add(username)
        self.client.sendServerMessage("%s muted." % username)
    
    @config("category", "player")
    @only_username_command
    def commandUnmute(self, username, fromloc, overriderank):
        "/unmute username - Guest\nLets you hear messages from this user again"
        if username in self.muted:
            self.muted.remove(username)
            self.client.sendServerMessage("%s unmuted." % username)
        else:
            self.client.sendServerMessage("%s wasn't muted to start with" % username)
    
    @config("category", "player")
    def commandMuted(self, username, fromloc, overriderank):
        "/muted - Guest\nLists people you have muted."
        if self.muted:
            self.client.sendServerList(["Muted:"] + list(self.muted))
        else:
            self.client.sendServerMessage("You haven't muted anyone.")