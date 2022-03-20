# What is this repo about?
This is custom fork of the original python mirror bot with custom added mirrors. 

Follow the instructions on the main repo to deploy.

# Added or changed features
## Change upload location
- Change folder id of gdrive for upload location temporarily until restart.

Usage: `/changeroot <googledrive_folder_id>`
 
## mirror_many
- Added mirroring multiple links in one command using default settings

Usage: `/mirror_many <single|batch> <link1,link2,link3>`

`single: add as as each individual task`

`batch: add all links as one task`
 
## XDCC
- Added downloading from xdcc

Usage: `/xdcc [server[:port]],]<channel> /msg <bot> xdcc <send|batch> <1|1-5>`

Eg: `/xdcc irc.xertion.org,MK /msg Rory|XDCC xdcc send #22969`

Default server is `irc.rizon.net`

## Onedrive
- Added support for both normal and recursive downloading from onedrive

Usage: `/onedrive <link>`

### Working links types

`https://<some>.sharepoint.com/:v:/g/personal/<some_email>/<some_id>?e=<some_code>` - Video link

`https://<some>.sharepoint.com/:f:/g/personal/<some_email>/<some_id>?e=<some_code>` - Folder link

`https://1drv.ms/u/s!<some_id>` - File link maybe(?)

#### To Do
- Check for more link schema (?)
- Add proper error handling maybe (?)

## Fembed
- Added downloading from fembed-like websites - https://fembed.com/
