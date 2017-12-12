
# self.database.set_image_requests_status(self.request_hash, 'imagesize_fail')
# self.database.set_image_requests_status(self.request_hash, 'signing_fail')
# self.database.set_image_requests_status(self.request_hash, 'build_fail')

# self.database.add_image( self.image_hash, self.as_array_build(), self.checksum, self.filesize, sysupgrade_image.replace(self.name + "-", ""), self.subtarget_in_name, self.profile_in_name, self.vanilla)
# self.database.done_build_job(self.request_hash, self.image_hash)
# self.database.add_manifest_packages(self.manifest_hash, manifest_packages)
# self.database.worker_register(worker_name, worker_address, worker_pubkey))
# self.database.worker_add_skill(self.worker_id, *imagebuilder, 'ready')
# self.database.worker_needed()
# self.database.worker_destroy(self.worker_id)
# self.database.get_build_job(*imagebuilder)
# self.database.worker_heartbeat(self.worker_id)
# self.database.subtarget_outdated(self.distro, self.release, self.target, self.subtarget):
# self.database.add_manifest(self.manifest_hash)
# self.database.c.execute("select 1 from images where image_hash = ?", self.image_hash)

# self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, "patch_fail")
# self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'download_fail')
#        if self.database.subtarget_outdated(self.distro, self.release, self.target, self.subtarget):
#        self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'ready')
#                self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'signature_fail')
#                self.database.set_imagebuilder_status(self.distro, self.release, self.target, self.subtarget, 'sha256sum_fail')
#        if self.database.subtarget_outdated(self.distro, self.release, self.target, self.subtarget):
#                self.database.insert_packages_available(self.distro, self.release, self.target, self.subtarget, packages)
