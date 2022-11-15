# Copyright (c) 2020-2022 Danilo G. Baio <dbaio@FreeBSD.org>
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

import urllib.parse
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Port(models.Model):
    origin = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=64)
    comment = models.CharField(max_length=192, blank=True)
    maintainer = models.EmailField()
    www = models.URLField(blank=True)

    # Categories
    main_category = models.CharField(max_length=64)
    categories = models.ManyToManyField(Category)

    def __str__(self):
        return self.origin


class Fallout(models.Model):
    port = models.ForeignKey(Port, on_delete=models.CASCADE)
    env = models.CharField(max_length=48)
    version = models.CharField(max_length=48)
    category = models.CharField(max_length=48)
    maintainer = models.EmailField()
    last_committer = models.EmailField()
    date = models.DateTimeField()
    log_url = models.URLField()
    build_url = models.URLField()
    report_url = models.URLField()
    server = models.CharField(max_length=48, blank=True)
    flavor = models.CharField(max_length=24, blank=True)

    def __str__(self):
        # head-arm64-default | net/findomain
        return self.env + " | " + self.port.origin


class Server(models.Model):
    name = models.CharField(max_length=48, unique=True)
    v4 = models.BooleanField(default=False)
    v6 = models.BooleanField(default=False)

    def __str__(self):
        return self.name
