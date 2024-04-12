from libb import Setting

Setting.unlock()

vendor = Setting()

vendor.FOO.ftp.hostname = '127.0.0.1'
vendor.FOO.ftp.username = 'foo'
vendor.FOO.ftp.password = 'bar'
vendor.FOO.ftp.port = 21

Setting.lock()
