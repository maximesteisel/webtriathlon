import time
import sys
import zipfile
import json

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = """Convert a save file in a psave format"""
    args = "infile [outfile]"
    can_import_settings = False
    requires_model_validation = False

    def handle(self, outfile="-", *args, **option):
        from webtriathlon.misc import get_db_version
        try:
            outfile = open(outfile, "w") if outfile != '-' else sys.stdout
            outfile.write(get_db_version())
        finally:
            outfile.close()
