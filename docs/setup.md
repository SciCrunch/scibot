# Database setup
```bash
export DBNAME=scibot_ASDF        # WARNING this WILL overwrite existing databases
scibot-dbsetup 5432 ${DBNAME}    # initial db, user, extension, and schema creation
scibot db-init ${DBNAME}         # create the schema from the hypothesis orm code
scibot api-sync ${DBNAME}        # retrieve and load existing annotations
```

# Installing services
TODO

# Starting services
## openrc
```bash
/etc/init.d/scibot-ws-sync start
```
## systemd 
```bash
systemctl start scibot-ws-sync
```
