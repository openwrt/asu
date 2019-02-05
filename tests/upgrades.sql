
drop function manifest_upgrades ( character varying, character varying, character varying, json) ;
-- function checks if a manifest is outdated
create or replace function manifest_upgrades (
    distro varchar, version varchar, target varchar, manifest json) 
    returns table(upgrades json) as $$
begin
    return query select united.upgrades from (
       select
            json_object_agg(package_name, package_versions) as upgrades
            from ( select
                    pa.package_name as package_name,
                    array[pa.package_version, mp.package_version] as package_versions
                from (select key as package_name, value as package_version
                    from json_each_text(manifest_upgrades.manifest)) as mp
                join packages_available pa using (package_name) where 
                    pa.distro = manifest_upgrades.distro and
                    pa.version = manifest_upgrades.version and
                    pa.target = manifest_upgrades.target and
                    pa.package_version != mp.package_version
            ) as upgrades) as united;
end
$$ LANGUAGE 'plpgsql';
