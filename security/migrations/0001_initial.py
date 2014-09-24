# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


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
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['users.User'], null=True, blank=True)),
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
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['users.User']", 'null': 'True', 'blank': 'True'})
        },
        u'users.user': {
            'Meta': {'object_name': 'User'},
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'role': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        }
    }

    complete_apps = ['security']