from django.db import models

class Announcement(models.Model):
    message = models.TextField("Message")

    def __unicode__(self):
        res = self.message[:100]
        if len(self.message) >= 100:
            return res + " ..."
        return res


