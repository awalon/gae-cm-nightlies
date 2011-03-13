from google.appengine.dist import use_library
use_library('django', '1.2')

import logging
import os

from lovely.jsonrpc import proxy

from django.utils import simplejson as json

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db


device_specific = {
    "ace": ["android_device_htc_ace", "htc-kernel-msm7x30"],
    "blade": ["android_device_zte_blade"],
    "bravo": ["cm-kernel", "android_device_htc_bravo"],
    "bravoc": ["cm-kernel", "android_device_htc_bravoc"],
    "buzz": ["android_device_htc_buzz"],
    "click": ["android_device_htc_click"],
    "crespo": ["android_device_samsung_crespo"],
    "encore": ["android_device_bn_encore"],
    "glacier": ["android_device_htc_glacier", "htc-kernel-msm7x30"],
    "hero": ["android_device_htc_hero"],
    "inc": ["android_device_htc_inc"],
    "heroc": ["android_device_htc_heroc"],
    "passion": ["android_device_htc_passion",
                "android_device_htc_passion-common"],
    "supersonic": ["android_device_htc_supersonic"],
    "vision": ["android_device_htc_vision", "htc-kernel-msm7x30"]
}


class Change(db.Model):
    id = db.IntegerProperty()
    project = db.StringProperty()
    subject = db.StringProperty()
    last_updated = db.StringProperty()


class ReviewsCron(webapp.RequestHandler):
    def get(self):
        amount = 40

        qa = self.request.get('amount')

        if qa: amount = int(qa)

        skipped = 0
        change_proxy = proxy.ServerProxy('http://review.cyanogenmod.com/gerrit/rpc/ChangeListService')
        changes = change_proxy.allQueryNext("status:merged","z",amount)['changes']
        known_ids = []

        q = db.GqlQuery("SELECT * FROM Change order by last_updated desc")

        known_ids = [int(c.id) for c in q.fetch(amount)]

        for c in changes:
            if c['id']['id'] in known_ids:
                skipped += 1
                continue

            change = Change(id=c['id']['id'],
                    project=c['project']['key']['name'].split("/")[1],
                    subject=c['subject'],
                    last_updated=c['lastUpdatedOn']
                    )
            change.put()

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("Cron ran, got %d changes from server, \
skipped %d changes" % (len(changes), skipped))


class MainPage(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path,
            {'devices':sorted(device_specific.keys())}))


class Ajax(webapp.RequestHandler):
    def common_projects(self):
        f = open('common_projects.txt', 'r')
        cp = [p.strip() for p in f.readlines()]
        f.closed

        return cp

    def filter(self, device):
        filtered = []

        q = Change.all()
        q.order('-last_updated')

        common = self.common_projects()

        for c in q.fetch(300):
            if c.project in common or c.project in device_specific[device]:
                filtered.append({"id": c.id, "project": c.project,
                    "subject": c.subject, "last_updated": c.last_updated})

        return filtered

    def get(self):
        device = "ace"

        qd = self.request.get('device')

        if qd and qd in device_specific.keys():
            device = qd

        self.response.headers['Content-Type'] = 'text/json'
        self.response.out.write(json.dumps(self.filter(device)))


application = webapp.WSGIApplication(
                                     [('/', MainPage), ('/changelog/', Ajax),
                                         ('/pull_reviews/', ReviewsCron)],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
