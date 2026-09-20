# Copyright (c) 2020-2026 Danilo G. Baio <dbaio@FreeBSD.org>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from django.db import models
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Port(models.Model):
    origin = models.CharField(max_length=128, unique=True)
    # The name is the origin without the category, so it can be nearly as long.
    name = models.CharField(max_length=128)
    comment = models.CharField(max_length=192, blank=True)
    maintainer = models.EmailField(db_index=True)
    www = models.URLField(blank=True)

    # Categories
    main_category = models.CharField(max_length=64)
    categories = models.ManyToManyField(Category)

    def __str__(self):
        return self.origin

    def get_absolute_url(self):
        # The origin is unique, so it is the natural key for the URL.
        return reverse('ports:detail', args=[self.origin])


class FalloutManager(models.Manager):

    def record(self, port, log_url, **fields):
        """Store what a source knows about the fallout of a build log

        A fallout reaches us twice: from the report the crawler reads, and
        from the builder's errors listing `find_orphan_fallouts` walks. The
        report is sent a second or so before the log is closed, and names a
        phase the head of the log may not reach, so the two never agree on
        every field. The log URL is what identifies the fallout, and the
        second source completes the row the first one made.

        What the source knows wins; a blank never replaces what is stored,
        as a source without a field says nothing about it.

        Arguments:
            port [Port] -- the port the log belongs to
            log_url [string] -- the build log
            fields -- everything else the source read
        Returns:
            [tuple] -- the fallout and whether it was created, as
                       `get_or_create` does
        """

        fallout, created = self.get_or_create(log_url=log_url,
                                              defaults={'port': port, **fields})
        if created:
            return fallout, True

        changed = [field for field, value in fields.items()
                   if value and getattr(fallout, field) != value]
        for field in changed:
            setattr(fallout, field, fields[field])
        if changed:
            fallout.save(update_fields=changed)

        return fallout, False


class Fallout(models.Model):
    port = models.ForeignKey(Port, on_delete=models.CASCADE)
    env = models.CharField(max_length=48, db_index=True)
    version = models.CharField(max_length=48)
    category = models.CharField(max_length=48, db_index=True)
    maintainer = models.EmailField(db_index=True)
    last_committer = models.EmailField()
    date = models.DateTimeField(db_index=True)
    # A log is written once, so its URL is what identifies a fallout: see
    # `FalloutManager.record`.
    log_url = models.URLField(unique=True)
    build_url = models.URLField()
    report_url = models.URLField()
    server = models.CharField(max_length=48, blank=True)
    flavor = models.CharField(max_length=24, blank=True)

    # Read from the poudriere header at the top of the build log, see
    # `ports.utils.LOG_HEADER_FIELDS`. Blank on the fallouts imported before
    # the crawler started keeping them, and on any log missing the block.
    package_name = models.CharField(max_length=128, blank=True)
    ports_top_commit = models.CharField(max_length=40, blank=True)
    port_dir_commit = models.CharField(max_length=40, blank=True)
    poudriere_version = models.CharField(max_length=48, blank=True)
    host_osversion = models.CharField(max_length=16, blank=True)
    jail_osversion = models.CharField(max_length=16, blank=True)

    objects = FalloutManager()

    def __str__(self):
        # head-arm64-default | net/findomain
        return self.env + " | " + self.port.origin


class BuildEnv(models.Model):
    name = models.CharField(max_length=48, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Envs"


class Server(models.Model):
    name = models.CharField(max_length=48, unique=True)
    v4 = models.BooleanField(default=False)
    v6 = models.BooleanField(default=False)
    envs = models.ManyToManyField(BuildEnv)

    def __str__(self):
        return self.name
