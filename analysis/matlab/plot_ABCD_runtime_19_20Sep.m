clear; clc; close all;

windowStart = datetime(2026,9,19,22,56,0);
windowEnd   = datetime(2026,9,20,11,0,0);

fileNames = {'sensor_data_2026-09-19(2).csv', ...
             'sensor_data_2026-09-20(4).csv'};

scriptDir = fileparts(mfilename('fullpath'));
if isempty(scriptDir), scriptDir = pwd; end
outputDir = fullfile(scriptDir,'ABCD_runtime_output');
if ~isfolder(outputDir), mkdir(outputDir); end

data = table(NaT(0,1),strings(0,1),'VariableNames',{'Time','Sensor'});
files = cell(1,2);
for f = 1:2
    files{f} = fullfile(scriptDir,fileNames{f});
    if ~isfile(files{f})
        if f == 1
            prompt = 'Select the 19 September CSV file';
        else
            prompt = 'Select the 20 September CSV file';
        end
        [name,folder] = uigetfile('*.csv',prompt);
        if isequal(name,0)
            error('File selection cancelled. Run again and select both CSV files.');
        end
        files{f} = fullfile(folder,name);
    end
    if f == 2 && strcmpi(files{1},files{2})
        error('Select two different daily CSV files.');
    end

    opts = detectImportOptions(files{f},'Delimiter',',');
    required = {'receive_time','sensor_name','type'};
    if ~all(ismember(required,opts.VariableNames))
        error('CSV must contain receive_time, sensor_name and type: %s',files{f});
    end
    opts = setvartype(opts,required,'string');
    opts.SelectedVariableNames = required;
    T = readtable(files{f},opts);

    T = T(strcmpi(strtrim(T.type),'sensor_data'),:);
    t = datetime(strtrim(T.receive_time), ...
        'InputFormat',"yyyy-MM-dd'T'HH:mm:ss.SSS");
    if any(isnat(t))
        error('Invalid receive_time value in: %s',files{f});
    end

    sensor = upper(strtrim(T.sensor_name));
    knownNode = ismember(sensor,["SENSOR_A","SENSOR_B","SENSOR_C","SENSOR_D"]);
    inWindow = t >= windowStart & t <= windowEnd;
    keep = knownNode & inWindow;
    part = table(t(keep),sensor(keep), ...
        'VariableNames',{'Time','Sensor'});
    data = [data; part]; %#ok<AGROW>
end

if isempty(data)
    error('No Node A-D DATA records were found in the selected time window.');
end
data = sortrows(unique(data,'rows'),{'Time','Sensor'});

nodeNames = ["SENSOR_A","SENSOR_B","SENSOR_C","SENSOR_D"];
nodeLabels = ["Node A","Node B","Node C","Node D"];
colours = [0.000 0.447 0.741; ...
           0.850 0.325 0.098; ...
           0.000 0.600 0.420; ...
           0.494 0.184 0.556];

fig = figure('Color','w','Position',[100 100 1100 450]);
ax = axes(fig,'Position',[0.10 0.20 0.87 0.66]);
hold(ax,'on');
counts = zeros(4,1);
firstTime = NaT(4,1);
lastTime = NaT(4,1);

for n = 1:4
    times = data.Time(data.Sensor == nodeNames(n));
    counts(n) = numel(times);
    if isempty(times), continue; end
    firstTime(n) = times(1);
    lastTime(n) = times(end);
    plot(ax,hours(times-windowStart),repmat(5-n,size(times)), ...
        '.','Color',colours(n,:),'MarkerSize',5,'LineStyle','none');
end

tickTimes = [windowStart, datetime(2026,9,20,0,0,0), ...
    datetime(2026,9,20,2,0,0), datetime(2026,9,20,4,0,0), ...
    datetime(2026,9,20,6,0,0), datetime(2026,9,20,8,0,0), ...
    datetime(2026,9,20,10,0,0), windowEnd];
tickLabels = {'22:56','00:00','02:00','04:00', ...
              '06:00','08:00','10:00','11:00'};
set(ax,'XTick',hours(tickTimes-windowStart),'XTickLabel',tickLabels, ...
    'YTick',1:4,'YTickLabel',{'Node D','Node C','Node B','Node A'}, ...
    'FontName','Arial','FontSize',13,'TickDir','out', ...
    'Box','off','XGrid','on','YGrid','off','GridAlpha',0.12);
xlim(ax,[0 hours(windowEnd-windowStart)]);
ylim(ax,[0.5 4.5]);
xlabel(ax,'Time (19-20 September 2026)','FontName','Arial','FontSize',14);
title(ax,'Node A-D data reception','FontName','Arial','FontSize',16, ...
    'FontWeight','bold','Interpreter','none');

firstTime.Format = 'yyyy-MM-dd HH:mm:ss.SSS';
lastTime.Format = 'yyyy-MM-dd HH:mm:ss.SSS';
summary = table(nodeLabels',counts,firstTime,lastTime, ...
    'VariableNames',{'Node','Records','FirstRecord','LastRecord'});
disp(summary);
writetable(summary,fullfile(outputDir,'ABCD_runtime_summary.csv'));

drawnow;
set(fig,'PaperUnits','inches');
paperSize = fig.Position(3:4)/get(groot,'ScreenPixelsPerInch');
set(fig,'PaperSize',paperSize,'PaperPosition',[0 0 paperSize]);
print(fig,fullfile(outputDir,'ABCD_runtime.png'),'-dpng','-r600');
print(fig,fullfile(outputDir,'ABCD_runtime.pdf'),'-dpdf','-painters');
savefig(fig,fullfile(outputDir,'ABCD_runtime.fig'));
fprintf('\nSaved to: %s\n',outputDir);
