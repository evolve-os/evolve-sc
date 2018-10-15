#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  This file is part of solus-sc
#
#  Copyright © 2013-2018 Ikey Doherty <ikey@solus-project.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#

import re

# Helpful for determing CVE matches.
CVE_HIT = re.compile(r"(CVE\-[0-9]+\-[0-9]+)")
CVE_URI = "https://cve.mitre.org/cgi-bin/cvename.cgi?name={}"

# All TNNNN hits are Maniphest Tasks
BUG_HIT = re.compile(r"T(\d+)")
BUG_URI = "https://dev.getsol.us"

# I know, it's evil. From:
# http://daringfireball.net/2010/07/improved_regex_for_matching_urls
GENERAL_URI = re.compile(r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d\
{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)\
))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>\
?«»“”‘’]))""")


class SpecialMarkdownParser:
    """ The SpecialMarkdownParser handles the two main kinds of markdown that
        the Solus Software Center will encounter:

         - AppStream Markdown
         - Git Commit Markdown (Solus specific)

        As such it needs to handle a few special cases:

         - CVE Identifiers
         - Differential IDs
         - Links
         - Bolding/Bullets
    """

    # Location in stream
    idx = 0

    # Buffer length
    max = 0

    # Our Thing to consume
    bfr = None

    # Anything we've managed to process
    consumed = None

    def __init__(self):
        self.reset()

    def reset(self):
        """ Reset the stream state entirely """
        self.idx = 0
        self.bfr = None
        self.consumed = []

    def peek(self, increment=1):
        """ Peek the next byte in the stream """
        if self.idx + increment > self.max:
            return None
        return self.bfr[self.idx + increment]

    def next(self):
        """ Move to the next byte in the stream """
        if self.idx + 1 > self.max:
            return None
        self.idx += 1
        return self.bfr[self.idx]

    def decode_changelog(self, text):
        """ This step is specialist and not for pure markdown appstream
            data, as it pertains to "normal" links and references in a
            Solus git commit
        """
        ret = ""

        block_elems = [
            "Summary",
            "Test Plan",
            "Maniphest Tasks",
        ]
        block_elem_ids = ["{}:".format(x) for x in block_elems]

        # Iterate all the lines
        for r in text.split("\n"):
            r = r.strip()

            # Handle Differential IDs by stylizing them
            for i, id in enumerate(block_elem_ids):
                if not r.startswith(id):
                    continue
                ret += "<b><u>{}</u></b>\n".format(block_elems[i])
                r = r.split(id)[1].strip()
                break

            r = CVE_HIT.sub(r'<a href="\1">\1</a>', r)
            r = BUG_HIT.sub(r'<a href="{}/T\1">T\1</a>'.format(BUG_URI), r)

            # Check if this is a bullet point
            if (r.startswith("- ") or r.startswith("* ")) and len(r) > 2:
                r = u' \u2022 ' + r[2:]

            for i in r.split(" "):
                uri = GENERAL_URI.match(i)
                if uri is not None:
                    uri_href = uri.group(0)
                    href = "<a href=\"{}\">{}</a>".format(uri_href, uri_href)
                    ret += href + i[len(uri_href):] + " "
                    continue
                # Just add the text
                ret += i + " "
                continue

            ret += "\n"
        return ret.strip()

    def consume(self, inp):
        """ Consume all input and output something usable. """
        self.reset()
        self.bfr = inp
        self.max = len(inp) - 1

        c = self.bfr[0]

        bold = False
        bold_bytes = '<b>'
        unbold_bytes = '</b>'
        underline = False
        underline_bytes = '<u>'
        ununderline_bytes = '</u>'
        bullet_bytes = '•'
        blank_start = True
        ignore_space = False

        code_bytes = '<span background=\'#C0C0C0\'><tt>'
        uncode_bytes = '</tt></span>'
        code_block = False
        code_one = False

        paragraph = ''
        bullet_chars = ['*', '-']
        in_bullet = False

        link_nom_start = -1
        link_nom_end = -1
        link_body_start = -1
        link_body_end = -1

        p_index = 0

        # Let's blast our way across the stream
        while c:
            if c == '\n':
                spaces = 0
                # Handle unterminated bold
                if bold:
                    paragraph += unbold_bytes
                    bold = False
                # Handle unterminated underline
                if underline:
                    paragraph += ununderline_bytes
                    underline = False
                # Handle unterminated code element
                if code_one:
                    paragraph += ' ' + uncode_bytes
                    code_one = False

                # Special case, opening code block
                if code_block:
                    if not blank_start:
                        paragraph += c
                    c = self.next()
                    continue

                if in_bullet:
                    ignore_space = True

                if blank_start:
                    # 2 newlines now
                    if len(paragraph) > 0:
                        self.consumed.append(paragraph.rstrip())
                    else:
                        in_bullet = False
                        ignore_space = False
                    paragraph = ''
                else:
                    paragraph += ' '

                # break multiline bullets when no longer bullet like
                if self.peek() and not self.peek().isspace() and in_bullet:
                    in_bullet = False
                    ignore_space = False
                    if len(paragraph) > 0:
                        self.consumed.append(paragraph.rstrip())
                    paragraph = ''

                blank_start = True
                c = self.next()
                continue
            if c == '*' and self.peek() == '*':
                if not code_block:
                    # Handle bolding
                    bold = not bold
                    if bold:
                        paragraph += bold_bytes
                    else:
                        paragraph += unbold_bytes
                    c = self.next()
                    c = self.next()
                    blank_start = False
                    continue
            if c == '_' and self.peek() == '_':
                if not code_block:
                    # Handle underline
                    underline = not underline
                    if underline:
                        paragraph += underline_bytes
                    else:
                        paragraph += ununderline_bytes
                    c = self.next()
                    c = self.next()
                    blank_start = False
                    continue
            elif c in bullet_chars and self.peek().isspace() and blank_start:
                if not code_block:
                    if len(paragraph) > 0:
                        self.consumed.append(paragraph.rstrip())
                    in_bullet = True
                    if spaces < 1:
                        spaces = 1
                    paragraph = (spaces * ' ') + bullet_bytes
                    c = self.next()
                    blank_start = False
                    ignore_space = False
                    continue
            elif c == '`':
                # Multi-block ?
                if self.peek() == '`' and self.peek(2) == '`':
                    code_block = not code_block
                    c = self.next()
                    c = self.next()
                    c = self.next()
                    if code_block:
                        paragraph += code_bytes
                    else:
                        paragraph += uncode_bytes
                        if len(paragraph) > 0:
                            self.consumed.append(paragraph.strip())
                        paragraph = ''
                    continue
                # OK it's just a normal bit of code
                code_one = not code_one
                if code_one:
                    paragraph += code_bytes + ' '
                else:
                    paragraph += ' ' + uncode_bytes
                c = self.next()
                continue

            p_index = len(paragraph)

            # Handle maybe-link-bits
            if c == '[':
                link_nom_start = p_index
            elif c == ']':
                link_nom_end = p_index
            elif c == '(':
                link_body_start = p_index
            elif c == ')':
                link_body_end = p_index

                p, change = self.relink(
                    paragraph,
                    link_nom_start,
                    link_nom_end,
                    link_body_start,
                    link_body_end)
                if change:
                    paragraph = p
                    c = self.next()
                    continue

            if ignore_space and c.isspace():
                c = self.next()
                spaces += 1
                continue
            else:
                spaces = 0

            ignore_space = False
            if not c.isspace():
                blank_start = False
            else:
                spaces = 0

            paragraph += c
            c = self.next()

        if len(paragraph) > 0:
            self.consumed.append(paragraph.rstrip())

    def emit(self):
        """ Return the converted text as a series of newline joined strings """
        return self.consumed

    def relink(self, text, lnk_start, lnk_end, h_start, h_end):
        """ Hyper crude, rebuild the paragraph with a link section in it """
        if lnk_start < 0 or lnk_end < 0:
            return None, False
        if h_start < 0 or h_end < 0:
            return None, False

        start_body = text[0:lnk_start]
        end_body = text[h_end+1:]

        lnk_start += 1
        h_start += 1
        if h_end < h_start:
            return text, False
        if lnk_end < lnk_start:
            return text, False

        link_name = text[lnk_start:lnk_end]
        link_target = text[h_start:h_end]
        link = "<a href=\"{}\">{}</a>".format(link_target, link_name)

        return "{}{}{}".format(start_body, link, end_body), True
