# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.conf import settings

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'LoggedRequest'
        db.create_table(u'security_loggedrequest', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('request_timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('method', self.gf('django.db.models.fields.CharField')(max_length=7)),
            ('path', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('queries', self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True)),
            ('headers', self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True)),
            ('body', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('is_secure', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('response_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True, blank=True)),
            ('type', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, null=True, blank=True)),
            ('error_description', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('has_response', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm[AUTH_USER_MODEL], null=True, blank=True)),
            ('ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
        ))
        db.send_create_signal(u'security', ['LoggedRequest'])


    def backwards(self, orm):
        # Deleting model 'LoggedRequest'
        db.delete_table(u'security_loggedrequest')


    models = {
        u'security.loggedrequest': {
            'Meta': {'ordering': "(u'-request_timestamp',)", 'object_name': 'LoggedRequest'},
            'body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'error_description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'has_response': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'is_secure': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'queries': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['%s']" % AUTH_USER_MODEL, 'null': 'True', 'blank': 'True'})
        },
        AUTH_USER_MODEL.lower(): {
            'Meta': {'object_name': AUTH_USER_MODEL.rsplit('.', 1)[1]},
        }
    }

    complete_apps = ['security']
