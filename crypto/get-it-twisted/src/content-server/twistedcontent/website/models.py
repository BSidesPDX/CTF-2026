from django.db import models

# Create your models here.

class EmailModel (models.Model):
    user_id = models.IntegerField()
    from_addr = models.CharField(max_length=500)
    subject_line = models.CharField(max_length=500)
    email_body = models.TextField()
    sent_date = models.CharField(max_length=500)
