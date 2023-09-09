# daily-tender-bot

This bot allows you to to create "daily tenders". It is a poll where chat decide who will lead today's daily meeting.
The word "tender" is used in a meaning of "offer", like "government tender".

## Start
You can build docker locally or pull release version: `docker pull monsieurpatate/daily-tender-bot:tag`. (for tags see [releases](https://github.com/MonsieurPatate/daily-tender-bot/releases))
You can aslo just create a deamon and run `py` script

## Commands
1. start - init bot in chat
2. info
3. add
4. delete
5. poll [time in UTC] ex: `poll 8.35`
6. repoll [name of a member to exclude from poll] ex: `repoll "fullName participant's name"`
7. free [name of a member to exclude from poll] [date in format: dd.MM.yyyy]
8. endpoll - force poll ending

