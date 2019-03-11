import conf
import sys
import json
import re
import subprocess
import datetime
import os

sys.path.append('phabapi/src')
from phabapi import PhabAPI, PhabHandler

class TeamsHandler(PhabHandler):
    ############
    # Messages #
    ############
    def on_diff_new(self, id, desc, act_user):
        log("on_diff_new: {}: {}".format(id, desc))

        diff = {
            'desc': desc,
            'owner': act_user,
        }
        self._set_diff(id, diff)

        message = "@{} created a new revision - *{}: {}*".format(act_user, id, desc)
        self._send_slack_message(message, conf.SLACK_TEAM_CHANNEL)

    def on_diff_request_changes(self, id, desc, act_user):
        log("on_diff_request_changes: {}: {} ({})".format(id, desc, act_user))

        message = "*{}: {}* requires changes to proceed.".format(id, desc)
        if act_user:
            if "-bot" in act_user:
                message = "{} has a failed build for *{}: {}*".format(act_user, id, desc)
            else:
                message = "@{} requested changes to *{}: {}*".format(act_user, id, desc)

        owner = self._get_diff_owner(id)
        channel = self._get_user_dm_channel(owner)
        if owner != act_user and channel:
            self._send_slack_message(message, channel)

    def on_diff_comment(self, id, desc, act_user, comment):
        log("on_diff_comment: {}: {} ({}) - {}".format(id, desc, act_user, comment))

        if "-bot" in act_user:
            return

        comment_format = "```{}```".format(comment) if comment else ""
        message = "@{} added a comment to *{}: {}*.\n{}".format(act_user, id, desc, comment_format)
        owner = self._get_diff_owner(id)
        channel = self._get_user_dm_channel(owner)
        if owner != act_user and channel:
            self._send_slack_message(message, channel)

    def on_diff_inline_comments(self, id, desc, act_user, comments):
        log("on_diff_inline_comments: {}: {} ({}) - {}".format(id, desc, act_user, comments))

        comments_str = '\n'.join(["```{}```".format(comment) for comment in comments if comment is not None])

        message = "@{} added inline comments to *{}: {}*.\n{}".format(act_user, id, desc, comments_str)
        owner = self._get_diff_owner(id)
        channel = self._get_user_dm_channel(owner)
        if owner != act_user and channel:
            self._send_slack_message(message, channel)

    def on_diff_ready_to_land(self, id, desc):
        log("on_diff_ready_to_land: {}: {}".format(id, desc))

        message = "*{}: {}* is accepted and ready to land.".format(id, desc)
        owner = self._get_diff_owner(id)
        channel = self._get_user_dm_channel(owner)
        if channel:
            self._send_slack_message(message, channel)

    def on_task_comment(self, id, desc, act_user, comment):
        log("on_task_comment: {}: {} ({}) - {}".format(id, desc, act_user, comment))

    def on_task_move(self, id, desc, act_user):
        log("on_task_move: {}: {} ({})".format(id, desc, act_user))

    ###########
    # Helpers #
    ###########
    def _get_user_dm_channel(self, user):
        return conf.SLACK_USER_IDS[user] if user and user in conf.SLACK_USER_IDS else None

    def _get_diff_owner(self, diff_id):
        diffs = self._read_all_diffs()
        return diffs[diff_id]['owner'] if diff_id in diffs else None

    def _set_diff(self, id, diff):
        diffs = self._read_all_diffs()
        diffs[id] = diff
        with open(conf.DIFF_FILE, 'w') as f:
            json.dump(diffs, f)

    def _get_diff(self, id):
        diff = None
        diffs = self._read_all_diffs()
        return diffs[id] if id in diffs else None

    def _read_all_diffs(self):
        diffs = {}
        with open(conf.DIFF_FILE, 'r') as f:
            diffs = json.load(f)

        return diffs

    def _send_slack_message(self, message, channel):
        message = re.sub(r'([DT][0-9]{4,})', r'<https://phab.duosec.org/\1|\1>', message)
        data = {
            'channel': channel,
            'text': message,
            'username': conf.SLACK_BOT_USER,
            'icon_emoji': conf.SLACK_BOT_ICON,
            'link_names': True
        }

        cmd = "curl -X POST -H 'Content-type: application/json' --data '{}' {}".format(json.dumps(data), conf.SLACK_HOOK)
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

def log(str, log_file="log"):
	p = "{} : {}".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'), str)
	print(p)
	with open("{}.txt".format(log_file), "a") as l:
		l.write("{}\n".format(p))

def main():
    if not os.path.exists(conf.DIFF_FILE):
        with open(conf.DIFF_FILE, 'w') as f:
            json.dump({}, f)

    PhabAPI(TeamsHandler(), conf.MAIL_SMTP, conf.MAIL_USER, conf.MAIL_PASS, conf.MAIL_LABEL).start()

if __name__ == "__main__":
    main()
