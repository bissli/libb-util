import config_sample

from libb import Setting

Setting.unlock()

# setting only in local
local = Setting()
local.local = 'Local'

# main setting overridden in locl
main = config_sample.main
main.override = 'Override'

# env settings specified in local
prod = config_sample.prod
prod.app1.dir = '/prod/app1/'
prod.app1.server= 'app1-prod-server'

dev = config_sample.dev
dev.app1.dir = '/dev/app1/'
dev.app1.server = 'app1-dev-server'

Setting.lock()
