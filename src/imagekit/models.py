import os
from datetime import datetime
from django.conf import settings
from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import ugettext_lazy as _

from imagekit.options import Options
from imagekit import specs


class IKModelBase(ModelBase):
    def __init__(cls, name, bases, attrs):
        
        parents = [b for b in bases if isinstance(b, IKModelBase)]
        if not parents:
            return
    
        user_opts = getattr(cls, 'IKConfig', None)
        opts = Options(user_opts)
        
        try:
            module = __import__(opts.config_module,  {}, {}, [''])
        except ImportError:
            raise ImportError('Unable to load imagekit config module: %s' % opts.config_module)
        
        for spec in [spec for spec in module.__dict__.values() \
                     if isinstance(spec, type) \
                     and issubclass(spec, specs.ImageSpec) \
                     and spec != specs.ImageSpec]:
            setattr(cls, spec.name(), specs.Descriptor(spec))
            opts.specs.append(spec)
            
        setattr(cls, '_ik', opts)


class IKModel(models.Model):
    """ Abstract base class implementing all core ImageKit functionality
    
    Subclasses of IKModel can override the inner IKConfig class to customize
    storage locations and other options.
    
    """
    __metaclass__ = IKModelBase

    class Meta:
        abstract = True
        
    class IKConfig:
        pass
        
    def admin_thumbnail_view(self):
        prop = getattr(self, 'admin_thumbnail', None)
        if prop is None:
            return 'An "admin_thumbnail" image spec has not been defined.'
        else:
            if hasattr(self, 'get_absolute_url'):
                return u'<a href="%s"><img src="%s"></a>' % \
                    (self.get_absolute_url(), prop.url)
            else:
                return u'<a href="%s"><img src="%s"></a>' % \
                    (self.ik_image_field.url, prop.url)
    admin_thumbnail_view.short_description = _('Thumbnail')
    admin_thumbnail_view.allow_tags = True
    
    @property
    def ik_image_field(self):
        return getattr(self, self._ik.image_field)
        
    @property        
    def cache_dir(self):
        """ Returns the path to the image cache directory """
        return os.path.join(os.path.dirname(self.ik_image_field.path),
                            self._ik.cache_dir)

    @property
    def cache_url(self):
        """ Returns a url pointing to the image cache directory """
        return '/'.join([os.path.dirname(self.ik_image_field.url),
                         self._ik.cache_dir])
    
    def _cleanup_cache_dirs(self):
        try:
            os.removedirs(self.cache_path)
        except:
            pass

    def _clear_cache(self):
        for spec in self._ik.specs:
            prop = getattr(self, spec.name())
            prop.delete()
        self._cleanup_cache_dirs()

    def _pre_cache(self):
        for spec in self._ik.specs:
            if spec.pre_cache:
                prop = getattr(self, spec.name())
                prop.create()

    def save(self, *args, **kwargs):
        #if self._get_pk_val():
        #    self._clear_cache()
        super(IKModel, self).save(*args, **kwargs)
        #self._pre_cache()

    def delete(self):
        assert self._get_pk_val() is not None, "%s object can't be deleted because its %s attribute is set to None." % (self._meta.object_name, self._meta.pk.attname)
        self._clear_cache()
        super(IKModel, self).delete()