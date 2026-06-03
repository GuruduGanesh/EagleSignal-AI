$TaskName = "EagleSignalAI-ResearchCollector"
Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Format-List *
Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue | Format-List *
