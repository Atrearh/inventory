param([string]$LastUpdated="None")
$ErrorActionPreference="Stop"
[Console]::OutputEncoding=$OutputEncoding=[Text.Encoding]::UTF8

function Clean($s) {if(!$s){""}else{($s-replace'[^\x20-\x7E]','').Trim()-replace'\s+False$',''}}

try{
    $list=[System.Collections.Generic.List[PSObject]]::new()
    foreach($path in "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*","HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"){
        Get-ItemProperty $path -ErrorAction SilentlyContinue|Where-Object{$_.DisplayName}|ForEach-Object{
            $name=Clean $_.DisplayName
            $date=if($_.InstallDate -and $_.InstallDate-match'^\d{8}$'){try{[datetime]::ParseExact($_.InstallDate,"yyyyMMdd",$null)}catch{$null}}else{$null}
            if($name){$list.Add([PSCustomObject]@{Name=Clean $_.DisplayName;Version=Clean $_.DisplayVersion;Publisher=Clean $_.Publisher;Date=if($date){$date.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") }else{$null}})}
        }
    }
    if($LastUpdated-ne"None"){
        $last=[datetime]::Parse($LastUpdated).ToUniversalTime()
        $filtered=[System.Collections.Generic.List[PSObject]]::new()
        try{
            $events=Get-WinEvent -LogName System -ErrorAction SilentlyContinue|Where-Object{($_.Id -eq 11707 -or $_.Id -eq 1033)-and $_.TimeCreated-gt$last}
            foreach($e in $events){
                $app=$e.Properties[0].Value
                $s=$list|Where-Object{$_.Name-eq$app}
                if($s-and($s.Publisher-ne"Microsoft Corporation"-or$s.Name-notmatch"Update|Security|Office|Hotfix|KB\d{7}")){$s.Date=$e.TimeCreated.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");$filtered.Add($s)}
            }
        }catch{
            foreach($s in $list){
                $date=$s.Date
                if($date-and[datetime]::Parse($date)-gt$last-and($s.Publisher-ne"Microsoft Corporation"-or$s.Name-notmatch"Update|Security|Office|Hotfix|KB\d{7}")){$filtered.Add($s)}
            }
        }
        $filtered|ConvertTo-Json -Depth 3 -Compress
    }else{@()|ConvertTo-Json -Compress}
}catch{Write-Error "software_info_changes.ps1: $($_.Exception.Message)";@()|ConvertTo-Json -Compress}