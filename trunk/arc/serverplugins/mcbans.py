# Arc is copyright 2009-2011 the Arc team and other contributors.
# Arc is licensed under the BSD 2-Clause modified License.
# To view more details, please see the "LICENSING" file in the "docs" folder of the Arc Package.

import ConfigParser

from arc.includes.mcbans_api import McBans

from arc.constants import *

class McBansServerPlugin():

    name = "McBansServerPlugin"

    hooks = {
        "prePlayerConnect": "connected",
        "playerQuit": "disconnected",
        "playerBanned": "banned",
        "playerUnbanned": "unbanned",
        "heartbeatSent": "callback"
    }

    def gotServer(self):
        self.logger.debug("[&1MCBans&f] Reading in API Key..")
        config = ConfigParser.RawConfigParser()
        try:
            config.read("config/plugins/mcbans.conf")
            api_key = config.get("mcbans", "apikey")
        except Exception as a:
            self.logger.error("[&1MCBans&f] &4Unable to find API key in config/plugins/mcbans.conf!")
            self.logger.error("[&1MCBans&f] &4%s" % a)
            self.has_api = False
        else:
            self.logger.debug("[&1MCBans&f] Found API key: &1%s&f" % api_key)
            self.logger.info("[&1MCBans&f] MCBans enabled!")
            self.handler = McBans(api_key)
            self.has_api = True
            try:
                self.threshold = config.getint("mcbans", "ban_threshold")
            except Exception as a:
                self.logger.warn("[&1MCBans&f] Unable to get the ban threshold, ignoring global ban reputations!")
                self.logger.warn("[&1MCBans&f] %s" % a)
                self.threshold = 0
            else:
                self.logger.info("[&1MCBans&f] Ban threshold is %s/10" % self.threshold)
            try:
                self.exceptions = config.options("exceptions")
            except Exception as a:
                self.logger.warn("[&1MCBans&f] Unable to get the exceptions list! Ignoring exceptions.")
                self.logger.warn("[&1MCBans&f] %s" % a)
                self.exceptions = []
            else:
                self.logger.info("[&1MCBans&f] %s exceptions loaded." % len(self.exceptions))
        del config

    def connected(self, data):
        if self.has_api:
            client = data["client"]
            data = self.handler.connect(client.username, client.transport.getPeer().host)
            try:
                error = value["error"]
            except:
                status = data["banStatus"]
                if status == u'n':
                    self.logger.info("[&1MCBans&f] User %s has a reputation of %s/10." % (client.username, data["playerRep"]))
                    client.sendServerMessage("[%sMCBans%s] You have a reputation of %s%s/10." % (COLOUR_BLUE, COLOUR_YELLOW, COLOUR_GREEN, data["playerRep"]))
                else:
                    self.logger.warn("[&1MCBans&f] User %s has a reputation of %s/10 with bans on record." % (client.username, data["playerRep"]))
                    client.sendServerMessage("[%sMCBans%s] Your reputation is %s%s/10%s with recorded bans." % (COLOUR_BLUE, COLOUR_YELLOW, COLOUR_RED, data["playerRep"], COLOUR_YELLOW))
                    if status == u'l':
                        if client.username not in self.exceptions:
                            self.logger.info("[&1MCBans&f] Kicking user %s as they are locally banned." % client.username)
                            client.sendError("[MCBans] You are locally banned.")
                        else:
                            self.logger.info("[&1MCBans&f] User %s has a local ban but is on the exclusion list." % client.username)
                    elif status == u's':
                        if client.username not in self.exceptions:
                            self.logger.info("[&1MCBans&f] Kicking user %s as they are banned in another server in the group." % client.username)
                            client.sendError("[MCBans] You banned on another server in this group.")
                        else:
                            self.logger.info("[&1MCBans&f] User %s is banned on another server in the group but is on the exclusion list." % client.username)
                    elif status == u't':
                        if client.username not in self.exceptions:
                            self.logger.info("[&1MCBans&f] Kicking user %s as they are temporarily banned." % client.username)
                            client.sendError("[MCBans] You are temporarily banned.")
                        else:
                            self.logger.info("[&1MCBans&f] User %s has a temporary ban but is on the exclusion list." % client.username)
                    elif status == u'i':
                        if client.username not in self.exceptions:
                            self.logger.info("[&1MCBans&f] Kicking user %s as they are banned on another IP." % client.username)
                            client.sendError("[MCBans] You are IP banned.")
                        else:
                            self.logger.info("[&1MCBans&f] User %s has a ban for another IP but is on the exclusion list." % client.username)
                if int(data["playerRep"]) < self.threshold:
                    if client.username not in self.exceptions:
                        self.logger.info("[&1MCBans&1] Kicking %s because their reputation of %s/10 is below the threshold!" % (client.username, data["playerRep"]))
                        client.sendError("Your MCBans reputation of %s/10 is too low!" % data["playerRep"])
                    else:
                        self.logger.info("[%sMCBans%s] %s has a reputation of %s/10 which is below the threshold, but is on the exceptions list." % (client.username, data["playerRep"]))
            else:
                self.factory.logger.error("MCBans error: %s" % str(error))

    def disconnected(self, data):
        if self.has_api:
            value = self.handler.disconnect(data["client"].username)
        try:
            error = value["error"]
        except:
            pass
        else:
            self.factory.logger.error("MCBans error: %s" % str(error))

    def banned(self, data):
        if self.has_api:
            value = self.handler.localBan(data["username"], self.factory.clients[data["username"]].getPeer().host if data["username"] in self.factory.clients.keys() else "Offline", data["reason"], data["admin"])
            try:
                error = value["error"]
            except:
                if value["result"] != u'y':
                    self.factory.logger.warn("Unable to add %s to the MCBans local ban list!")
            else:
                self.factory.logger.error("MCBans error: %s" % str(error))

    def unbanned(self, data):
        if self.has_api:
            value = self.handler.unban(data["username"], "Local")
            try:
                error = value["error"]
            except:
                if value["result"] != u'y':
                    self.factory.logger.warn("Unable to remove %s from the MCBans local ban list!")
            else:
                self.factory.logger.error("MCBans error: %s" % str(error))

    def callback(self):
        if self.has_api:
            version = "9.0.0.1"
            maxplayers = self.factory.max_clients
            playerlist = []
            for element in self.factory.usernames.keys():
                playerlist.append(element)
            done = ",".join(playerlist)
            value = self.handler.callBack(maxplayers, done, version)
            try:
                error = value["error"]
            except:
                pass
            else:
                self.factory.logger.error("MCBans error: %s" % str(error))

serverPlugin = McBansServerPlugin