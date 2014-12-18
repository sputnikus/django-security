# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.conf import settings

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'LoggedRequest.has_response'
        db.delete_column(u'security_loggedrequest', 'has_response')


        # Changing field 'LoggedRequest.status'
        db.alter_column(u'security_loggedrequest', 'status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1))

        # Changing field 'LoggedRequest.request_timestamp'
        db.alter_column(u'security_loggedrequest', 'request_timestamp', self.gf('django.db.models.fields.DateTimeField')())

        # Changing field 'LoggedRequest.response_code'
        db.alter_column(u'security_loggedrequest', 'response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=200))

        # Changing field 'LoggedRequest.response_timestamp'
        db.alter_column(u'security_loggedrequest', 'response_timestamp', self.gf('django.db.models.fields.DateTimeField')())

        # Changing field 'LoggedRequest.type'
        db.alter_column(u'security_loggedrequest', 'type', self.gf('django.db.models.fields.PositiveSmallIntegerField')())

    def backwards(self, orm):
        # Adding field 'LoggedRequest.has_response'
        db.add_column(u'security_loggedrequest', 'has_response',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


        # Changing field 'LoggedRequest.status'
        db.alter_column(u'security_loggedrequest', 'status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True))

        # Changing field 'LoggedRequest.request_timestamp'
        db.alter_column(u'security_loggedrequest', 'request_timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True))

        # Changing field 'LoggedRequest.response_code'
        db.alter_column(u'security_loggedrequest', 'response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True))

        # Changing field 'LoggedRequest.response_timestamp'
        db.alter_column(u'security_loggedrequest', 'response_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True))

        # Changing field 'LoggedRequest.type'
        db.alter_column(u'security_loggedrequest', 'type', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True))

    models = {
        u'security.loggedrequest': {
            'Meta': {'ordering': "(u'-request_timestamp',)", 'object_name': 'LoggedRequest'},
            'body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'error_description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'is_secure': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'queries': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['%s']" % AUTH_USER_MODEL, 'null': 'True', 'blank': 'True'})
        },
        AUTH_USER_MODEL.lower(): {
            'Meta': {'object_name': AUTH_USER_MODEL.rsplit('.', 1)[1]},
        }
    }

    complete_apps = ['security']
