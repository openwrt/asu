module("luci.controller.attended-sysupgrade", package.seeall)

function index()
        entry({"admin", "system", "attended_sysupgrade"}, template("attended-sysupgrade"), _("Attended Sysupgrade"), 1)
end
