# attendedsysupgrade
## Ansible Playbook(s)

### Caveats

* Due to database operations as unprivileged users, this playbook must connect
as a privileged (root) user. It is recommended to do so with SSH keys, or by
running Ansible directly on the host to be managed.
  * Any suggestions on avoiding this would be welcomed.