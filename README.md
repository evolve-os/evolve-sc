solus-sc
--------

Software Center component of the Solus Operating System. Currently undergoing
an overhaul to drop all the stupidity and slowness that it managed to gather
over the years.

Solus Software Center is a [Solus project](https://getsol.us/)

![logo](https://build.getsol.us/logo.png)

**Why not use GNOME Software?**

GNOME Software relies on several layers of abstraction to address limitations
in the underlying package formats that cannot be extended to represent the
required metadata.

GNOME Software also fits a different design pattern from an architectural view
to Solus itself. The requirement to reboot even for trivial updates isn't
acceptable within the Solus platform.

The further integrations of several competing standards for application isolation
within the framework also isn't something desirable for Solus. We provide native
optimized runtimes of our own, as such the performance of Solus  would be
*severely impacted* by the introduction of watered down third party runtimes.

Lastly, the Solus stack pre-dates GNOME Software, and Solus mandates tight integration
between components. Nuff said.


Testing
-------

Clone the repo, and then install appstream-glib::

    sudo eopkg it appstream-glib

Now you'll need the appdata::

    sudo eopkg it appstream-data

Now just run the main launcher in this repo (don't ctrl+c, it'll explode)::

    ./new.py

License
-------

Copyright © 2013-2018 Ikey Doherty

This software is available under the terms of the GPL-2.0 license.
Please see `LICENSE` for details.
