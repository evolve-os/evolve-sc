from setuptools import setup


setup(
    name            = "solus-sc",
    version         = "15.0",
    author          = "Ikey Doherty",
    author_email    = "ikey@solus-project.com",
    description     = ("Solus Software Center"),
    license         = "GPL-2.0",
    url             = "https://github.com/solus-project/os-installer",
    packages        = ['solus_sc', 'eopkg_assist', 'solus_update'],
    scripts         = ['solus-sc', 'solus-update-checker'],
    classifiers     = [ "License :: OSI Approved :: GPL-2.0 License"],
    package_data    = {'solus_sc': ['data/update_dialog.ui', 'data/styling.css', 'data/arc.css', 'data/settings.ui']},
    data_files      = [("/usr/share/applications", ["data/solus-sc.desktop"]),
                       ("/usr/share/dbus-1/system-services", ["data/dbus-1/system-services/com.solus_project.eopkgassist.service"]),
                       ("/etc/dbus-1/system.d", ["data/system.d/com.solus_project.eopkgassist.conf"]),
                       ("/usr/share/polkit-1/actions", ["data/polkit-1/actions/com.solus_project.eopkgassist.policy"]),
                       ("/usr/share/glib-2.0/schemas", ["data/com.solus-project.software-center.gschema.xml"]),
                       ("/usr/share/xdg/autostart", ["data/solus-update.desktop"]),
                       ("/usr/libexec", ["eopkg-assist-wrapper"])]
)
