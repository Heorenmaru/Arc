import shutil, os, traceback

from twisted.internet import reactor

from core.constants import *
from core.decorators import *
from core.globals import *
from core.plugins import ProtocolPlugin

class IsoImagePlugin(ProtocolPlugin):

    commands = {
        "isoimage": "commandIso",
    }

    @config("rank", "op")
    def commandIso(self, parts, fromloc, overriderank):
        "/isoimage [1-4] - Op\nCreates an IsoImage of the current world."
        if len(parts) == 2:
            if str(parts[1]) in "1234":
                angle = parts[1]
            else:
                self.client.sendServerMessage('You must provide 1-4 for the angle.')
                return
        else:
            angle = 1
        world = self.client.world
        pathname = os.getcwd()
        savepath = pathname + "/core/isoimage/images/"
        worldname = world.basename.split("/")[1]
        worldpath = pathname + "/worlds/" + worldname
        try:
            os.chdir(pathname + "/core/isoimage/")
            if checkos() == "Windows":
                os.system('java -Xms512M -Xmx1024M -cp minecraft-server.jar; OrigFormat save "%s" server_level.dat' % worldpath)
                os.system('java -Xms128M -Xmx1024M -cp minecraft-server.jar;IsoCraft++.jar isocraft server_level.dat tileset.png output.png %s -1 -1 -1 -1 -1 -1 visible'%str(angle))
            else:
                os.system('java -Xms512M -Xmx1024M -cp minecraft-server.jar: OrigFormat save "%s" server_level.dat' % worldpath)
                os.system('java -Xms128M -Xmx1024M -cp minecraft-server.jar:IsoCraft++.jar isocraft server_level.dat tileset.png output.png %s -1 -1 -1 -1 -1 -1 visible'%str(angle))
            shutil.move("output.png", "images/%s%s.png" % (worldname, str(angle)))
            os.chdir(pathname)
            self.client.sendServerMessage('Isoimage %s has been created.' %(worldname + str(angle) + ".png"))
        except:
            self.client.sendSplitServerMessage(traceback.format_exc().replace("Traceback (most recent call last):", ""))
            self.client.sendSplitServerMessage("Internal Server Error - Traceback (Please report this to the Server Staff or the iCraft Team, see /about for contact info)")
            self.client.logger.error(traceback.format_exc())
            os.chdir(pathname)