function plot_offline_operation()

clc;
close all;

[fileName, filePath] = uigetfile( ...
    {'*.txt','Text log files (*.txt)'}, ...
    'Select GATE02_offline_monitor.txt');

if isequal(fileName,0)
    disp('File selection cancelled.');
    return;
end

fullFile = fullfile(filePath,fileName);

fprintf('\nSelected file:\n%s\n\n',fullFile);

rawText = fileread(fullFile);

lines = splitlines(string(rawText));

nLines = numel(lines);

sampleNumber = [];
sampleTime   = NaT(0,1);

networkState = [];
gatewayState = [];

rawLineCount = [];
sensorSeq    = [];

i = 1;

while i <= nLines

    lineNow = strtrim(lines(i));

    sampleToken = regexp( ...
        char(lineNow), ...
        '^=== SAMPLE\s+(\d+)\s+===$', ...
        'tokens', ...
        'once');

    if isempty(sampleToken)
        i = i + 1;
        continue;
    end

    currentSample = str2double(sampleToken{1});

    j = i + 1;

    while j <= nLines && strlength(strtrim(lines(j))) == 0
        j = j + 1;
    end

    if j > nLines
        break;
    end

    currentTime = parseDateTimeLine(lines(j));

    currentNetwork = 0;
    currentGateway = 0;
    currentRawCount = NaN;
    currentSequence = NaN;

    k = j + 1;

    while k <= nLines

        L = strtrim(lines(k));

        if startsWith(L,'=== SAMPLE') || ...
           startsWith(L,'=== GATE02 OFFLINE TEST END')
            break;
        end

        if strcmp(L,'--- Network ---')

            q = k + 1;

            while q <= nLines && strlength(strtrim(lines(q))) == 0
                q = q + 1;
            end

            if q <= nLines

                nextLine = strtrim(lines(q));

                if startsWith(nextLine,'---')
                    currentNetwork = 0;
                else

                    ipMatch = regexp( ...
                        char(nextLine), ...
                        '\d{1,3}(\.\d{1,3}){3}', ...
                        'once');

                    if ~isempty(ipMatch)
                        currentNetwork = 1;
                    else
                        currentNetwork = 0;
                    end

                end
            end
        end

        if strcmp(L,'--- Gateway service ---')

            if k+1 <= nLines

                nextLine = strtrim(lines(k+1));

                if strcmpi(nextLine,'active')
                    currentGateway = 1;
                else
                    currentGateway = 0;
                end

            end
        end

        if strcmp(L,'--- Raw line count ---')

            if k+1 <= nLines

                nextLine = strtrim(lines(k+1));

                countToken = regexp( ...
                    char(nextLine), ...
                    '^(\d+)\s+', ...
                    'tokens', ...
                    'once');

                if ~isempty(countToken)
                    currentRawCount = str2double(countToken{1});
                end

            end
        end

        if strcmp(L,'--- Last raw record ---')

            if k+1 <= nLines

                csvLine = char(lines(k+1));

                seqToken = regexp( ...
                    csvLine, ...
                    '^[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,[^,]+,(\d+),', ...
                    'tokens', ...
                    'once');

                if ~isempty(seqToken)
                    currentSequence = str2double(seqToken{1});
                end

            end
        end

        k = k + 1;

    end

    sampleNumber(end+1,1) = currentSample; %#ok<AGROW>
    sampleTime(end+1,1)   = currentTime; %#ok<AGROW>

    networkState(end+1,1) = currentNetwork; %#ok<AGROW>
    gatewayState(end+1,1) = currentGateway; %#ok<AGROW>

    rawLineCount(end+1,1) = currentRawCount; %#ok<AGROW>
    sensorSeq(end+1,1)    = currentSequence; %#ok<AGROW>

    i = k;

end

processedUpdateTime = NaT(0,1);

for i = 1:nLines

    L = strtrim(lines(i));

    if ~contains(L,'processed_data_')
        continue;
    end

    timeToken = regexp( ...
        char(L), ...
        '^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\.(\d+)', ...
        'tokens', ...
        'once');

    if isempty(timeToken)
        continue;
    end

    datePart = timeToken{1};
    timePart = timeToken{2};
    fraction = timeToken{3};

    if length(fraction) >= 3
        millis = fraction(1:3);
    else
        millis = [fraction repmat('0',1,3-length(fraction))];
    end

    timeString = sprintf( ...
        '%s %s.%s', ...
        datePart, ...
        timePart, ...
        millis);

    try

        dt = datetime( ...
            timeString, ...
            'InputFormat','yyyy-MM-dd HH:mm:ss.SSS');

        processedUpdateTime(end+1,1) = dt; %#ok<AGROW>

    catch
    end

end

processedUpdateTime = processedUpdateTime(~isnat(processedUpdateTime));

if ~isempty(processedUpdateTime)
    processedUpdateTime = unique(processedUpdateTime);
end

valid = ...
    ~isnat(sampleTime) & ...
    isfinite(sensorSeq) & ...
    isfinite(rawLineCount);

sampleNumber = sampleNumber(valid);
sampleTime   = sampleTime(valid);

networkState = networkState(valid);
gatewayState = gatewayState(valid);

rawLineCount = rawLineCount(valid);
sensorSeq    = sensorSeq(valid);

if isempty(sampleTime)
    error('No valid GATE02 samples were found.');
end

[sampleTime, order] = sort(sampleTime);

sampleNumber = sampleNumber(order);
networkState = networkState(order);
gatewayState = gatewayState(order);

rawLineCount = rawLineCount(order);
sensorSeq    = sensorSeq(order);

offlineIndex = find(networkState == 0,1,'first');

if isempty(offlineIndex)

    offlineTime = NaT;
    warning('No network-disconnected sample was detected.');

else

    offlineTime = sampleTime(offlineIndex);

end

fprintf('\n');
fprintf('GATE02 OFFLINE TEST SUMMARY\n');
fprintf('====================================================\n');

fprintf('Number of samples             : %d\n', ...
    numel(sampleTime));

fprintf('First sample                  : %s\n', ...
    datestr(sampleTime(1),'yyyy-mm-dd HH:MM:SS.FFF'));

fprintf('Final sample                  : %s\n', ...
    datestr(sampleTime(end),'yyyy-mm-dd HH:MM:SS.FFF'));

if ~isnat(offlineTime)

    fprintf('First no-network sample       : %s\n', ...
        datestr(offlineTime,'yyyy-mm-dd HH:MM:SS.FFF'));

end

fprintf('Sensor A sequence: first/last : %d / %d\n', ...
    sensorSeq(1),sensorSeq(end));

fprintf('Raw line count: first/last    : %d / %d\n', ...
    rawLineCount(1),rawLineCount(end));

fprintf('Gateway active samples        : %d / %d\n', ...
    sum(gatewayState == 1), ...
    numel(gatewayState));

offlineSamples = find(networkState == 0);

if ~isempty(offlineSamples)

    firstOffline = offlineSamples(1);
    lastOffline  = offlineSamples(end);

    offlineSpan = ...
        sampleTime(lastOffline) - ...
        sampleTime(firstOffline);

    sequenceIncrease = ...
        sensorSeq(lastOffline) - ...
        sensorSeq(firstOffline);

    rowIncrease = ...
        rawLineCount(lastOffline) - ...
        rawLineCount(firstOffline);

    fprintf('\n');
    fprintf('CONFIRMED NETWORK-DISCONNECTED INTERVAL\n');
    fprintf('----------------------------------------------------\n');

    fprintf('First disconnected sample : %s\n', ...
        datestr( ...
        sampleTime(firstOffline), ...
        'yyyy-mm-dd HH:MM:SS.FFF'));

    fprintf('Last disconnected sample  : %s\n', ...
        datestr( ...
        sampleTime(lastOffline), ...
        'yyyy-mm-dd HH:MM:SS.FFF'));

    fprintf('Observed disconnected span: %.3f min\n', ...
        minutes(offlineSpan));

    fprintf('Sensor A sequence increase: %d\n', ...
        sequenceIncrease);

    fprintf('Raw-record increase       : %d\n', ...
        rowIncrease);

end

fprintf('\n');
fprintf('PROCESSING OUTPUT UPDATES DURING TEST\n');
fprintf('----------------------------------------------------\n');

if isempty(processedUpdateTime)

    fprintf('No processed-data timestamps were parsed.\n');

else

    for i = 1:numel(processedUpdateTime)

        if processedUpdateTime(i) >= sampleTime(1) && ...
           processedUpdateTime(i) <= sampleTime(end)

            fprintf('%s\n', ...
                datestr( ...
                processedUpdateTime(i), ...
                'yyyy-mm-dd HH:MM:SS.FFF'));

        end

    end

end

fig = figure( ...
    'Color','w', ...
    'Units','pixels', ...
    'Position',[100 70 1100 760]);

tl = tiledlayout( ...
    fig, ...
    2,1, ...
    'TileSpacing','compact', ...
    'Padding','compact');

ax1 = nexttile(tl,1);

hold(ax1,'on');

plot( ...
    ax1, ...
    sampleTime, ...
    sensorSeq, ...
    '-o', ...
    'LineWidth',1.8, ...
    'MarkerSize',5.5, ...
    'DisplayName','Sensor A sequence');

ylabel( ...
    ax1, ...
    'Sensor A sequence', ...
    'FontName','Times New Roman', ...
    'FontSize',14);

grid(ax1,'on');
ax1.GridAlpha = 0.18;

box(ax1,'off');

ax1.FontName = 'Times New Roman';
ax1.FontSize = 12;
ax1.LineWidth = 1;

xlim(ax1,[sampleTime(1) sampleTime(end)]);

if ~isnat(offlineTime)

    xline( ...
        ax1, ...
        offlineTime, ...
        '--', ...
        'Network unavailable', ...
        'LineWidth',1.2, ...
        'LabelHorizontalAlignment','left', ...
        'LabelVerticalAlignment','top', ...
        'FontName','Times New Roman', ...
        'FontSize',11);

end

processingTimesInPlot = processedUpdateTime( ...
    processedUpdateTime >= sampleTime(1) & ...
    processedUpdateTime <= sampleTime(end));

if ~isnat(offlineTime)

    processingTimesOffline = processingTimesInPlot( ...
        processingTimesInPlot >= offlineTime);

else

    processingTimesOffline = NaT(0,1);

end

for i = 1:numel(processingTimesOffline)

    xline( ...
        ax1, ...
        processingTimesOffline(i), ...
        ':', ...
        'Local processing update', ...
        'LineWidth',1.1, ...
        'LabelHorizontalAlignment','left', ...
        'LabelVerticalAlignment','bottom', ...
        'FontName','Times New Roman', ...
        'FontSize',10);

end

ax2 = nexttile(tl,2);

hold(ax2,'on');

stairs( ...
    ax2, ...
    sampleTime, ...
    networkState, ...
    '-o', ...
    'LineWidth',1.8, ...
    'MarkerSize',5, ...
    'DisplayName','Network');

gatewayPlotState = gatewayState + 1;

stairs( ...
    ax2, ...
    sampleTime, ...
    gatewayPlotState, ...
    '-s', ...
    'LineWidth',1.8, ...
    'MarkerSize',5, ...
    'DisplayName','Gateway service');

ylim(ax2,[-0.25 2.25]);

ax2.YTick = [0 1 2];

ax2.YTickLabel = { ...
    'Network unavailable', ...
    'Network available', ...
    'Gateway active'};

ylabel( ...
    ax2, ...
    'Operational state', ...
    'FontName','Times New Roman', ...
    'FontSize',14);

grid(ax2,'on');
ax2.GridAlpha = 0.18;

box(ax2,'off');

ax2.FontName = 'Times New Roman';
ax2.FontSize = 12;
ax2.LineWidth = 1;

xlim(ax2,[sampleTime(1) sampleTime(end)]);

if ~isnat(offlineTime)

    xline( ...
        ax2, ...
        offlineTime, ...
        '--', ...
        'LineWidth',1.2, ...
        'HandleVisibility','off');

end

startTick = ...
    dateshift(sampleTime(1),'start','minute');

endTick = ...
    dateshift(sampleTime(end),'start','minute');

tickTimes = startTick:minutes(2):endTick;

ax1.XTick = tickTimes;
ax2.XTick = tickTimes;

ax1.XTickLabel = [];

tickLabels = cell(numel(tickTimes),1);

for i = 1:numel(tickTimes)

    tickLabels{i} = sprintf( ...
        '%02d:%02d', ...
        hour(tickTimes(i)), ...
        minute(tickTimes(i)));

end

ax2.XTickLabel = tickLabels;

try
    ax1.XAxis.SecondaryLabel.Visible = 'off';
catch
end

try
    ax2.XAxis.SecondaryLabel.Visible = 'off';
catch
end

xlabel( ...
    ax2, ...
    'Gateway clock on 23 September 2026', ...
    'FontName','Times New Roman', ...
    'FontSize',13);

linkaxes([ax1 ax2],'x');

legend( ...
    ax2, ...
    'Location','best', ...
    'FontName','Times New Roman', ...
    'FontSize',11);

pngFile = fullfile( ...
    filePath, ...
    'Offline_Operation.png');

pdfFile = fullfile( ...
    filePath, ...
    'Offline_Operation.pdf');

exportgraphics( ...
    fig, ...
    pngFile, ...
    'Resolution',600);

exportgraphics( ...
    fig, ...
    pdfFile, ...
    'ContentType','vector');

fprintf('\n');
fprintf('FIGURE EXPORTED\n');
fprintf('====================================================\n');

fprintf('PNG:\n%s\n\n',pngFile);

fprintf('PDF:\n%s\n\n',pdfFile);

fprintf('Done.\n');

end

function dt = parseDateTimeLine(line)

s = strtrim(string(line));

dt = NaT;

try

    dt = datetime( ...
        s, ...
        'InputFormat','yyyy-MM-dd HH:mm:ss.SSS');

catch

    try

        dt = datetime( ...
            s, ...
            'InputFormat','yyyy-MM-dd HH:mm:ss');

    catch
    end

end

end
