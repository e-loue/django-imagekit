from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings
import re
from ...registry import generator_registry, cachefile_registry
from ...exceptions import MissingSource


class Command(BaseCommand):
    help = ("""Generate files for the specified image generators (or all of them if
none was provided). Simple, glob-like wildcards are allowed, with *
matching all characters within a segment, and ** matching across
segments. (Segments are separated with colons.) So, for example,
"a:*:c" will match "a:b:c", but not "a:b:x:c", whereas "a:**:c" will
match both. Subsegments are always matched, so "a" will match "a" as
well as "a:b" and "a:b:c".""")
    args = '[generator_ids]'

    def handle(self, *args, **options):
        generators = generator_registry.get_ids()

        if args:
            patterns = self.compile_patterns(args)
            generators = (id for id in generators if any(p.match(id) for p in patterns))

        for generator_id in generators:
            self.stdout.write('Validating generator: %s\n' % generator_id)
            for image_file in cachefile_registry.get(generator_id):
                if image_file.name:
                    cache_key = 'imagekit_generation:%s' % image_file.name
                    self.stdout.write('  %s\n' % image_file.name)
                    if cache.get(cache_key):
                        continue
                    if image_file.storage.exists(image_file.name):
                        cache.set(cache_key, True, settings.IMAGEKIT_BATCH_GENERATION_CACHE_LIFETIME)
                        continue
                    try:
                        image_file.generate()
                    except MissingSource as err:
                        self.stdout.write('\t No source associated with\n')
                    except Exception as err:
                        self.stdout.write('\tFailed %s\n' % (err))
                    else:
                        cache.set(cache_key, True, settings.IMAGEKIT_BATCH_GENERATION_CACHE_LIFETIME)

    def compile_patterns(self, generator_ids):
        return [self.compile_pattern(id) for id in generator_ids]

    def compile_pattern(self, generator_id):
        parts = re.split(r'(\*{1,2})', generator_id)
        pattern = ''
        for part in parts:
            if part == '*':
                pattern += '[^:]*'
            elif part == '**':
                pattern += '.*'
            else:
                pattern += re.escape(part)
        return re.compile('^%s(:.*)?$' % pattern)
