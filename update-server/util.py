import urllib.request
from database import Database
import re

database = Database()

target_website = urllib.request.urlopen("https://downloads.lede-project.org/releases/17.01.0/targets/").read().decode('utf-8')
target_pattern = r'<tr><td class="n"><a href=".+">(\w+)</a>/</td><td class="s">-</td><td class="d">.+</td></tr>'
targets = re.findall(target_pattern, target_website)

for target in targets:
    subtarget_website = urllib.request.urlopen("https://downloads.lede-project.org/releases/17.01.0/targets/%s" % target).read().decode('utf-8')
    subtarget_pattern = r'<tr><td class="n"><a href=".+">(\w+)</a>/</td><td class="s">-</td><td class="d">.+</td></tr>'
    subtargets = re.findall(subtarget_pattern, subtarget_website)
    print(target, subtargets)
    database.insert_target(target, subtargets)

        

print(targets)
