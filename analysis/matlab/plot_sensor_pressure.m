function plot_sensor_pressure

useTimeWindow = false;
startTime = datetime(2026,9,14,17,36,0);
endTime = datetime(2026,9,14,21,36,0);

[file, folder] = uigetfile({'*.csv;*.xlsx;*.xls', 'Sensor data (*.csv, *.xlsx, *.xls)'}, 'Select sensor data');
if isequal(file, 0), return; end
csvPath = fullfile(folder, file);

fid = fopen(csvPath, 'rb');
if fid < 0, error('Cannot open the selected file.'); end
signature = fread(fid, 4, '*uint8')';
fclose(fid);
[~,~,ext] = fileparts(csvPath);
readPath = csvPath;
isZip = isequal(signature, uint8([80 75 3 4]));
if isZip && ~strcmpi(ext, '.xlsx')
    readPath = [tempname '.xlsx'];
    [copied, message] = copyfile(csvPath, readPath);
    if ~copied, error('%s', message); end
    cleanupFile = onCleanup(@() delete(readPath)); %#ok<NASGU>
    fprintf('Excel content detected inside the selected file.\n');
end
if isZip || any(strcmpi(ext, {'.xlsx','.xls'}))
    opts = detectImportOptions(readPath, 'FileType', 'spreadsheet');
else
    opts = detectImportOptions(readPath, 'FileType', 'text');
end
required = {'receive_time', 'sensor_name', 'pressure_hpa'};
if ~all(ismember(required, opts.VariableNames))
    error('Required columns: receive_time, sensor_name, pressure_hpa. Found: %s', strjoin(opts.VariableNames, ', '));
end
opts.SelectedVariableNames = required;
opts = setvartype(opts, {'receive_time', 'sensor_name'}, 'string');
opts = setvartype(opts, 'pressure_hpa', 'double');
T = readtable(readPath, opts);

t = datetime(strtrim(string(T.receive_time)), 'InputFormat', 'yyyy-MM-dd''T''HH:mm:ss.SSS');
node = strtrim(T.sensor_name);
y = T.pressure_hpa;
y(~isfinite(y)) = NaN;
names = ["Sensor_A", "Sensor_B", "Sensor_C", "Sensor_D"];
keep = ~isnat(t) & ismember(node, names);
if ~any(keep)
    error('CSV has no recognised Sensor_A/B/C/D records with valid timestamps.');
end
availableTime = t(keep);
fprintf('CSV time range: %s to %s\n', char(min(availableTime)), char(max(availableTime)));
if useTimeWindow
    if endTime <= startTime
        error('endTime must be later than startTime.');
    end
    keep = keep & t >= startTime & t < endTime;
    if ~any(keep)
        error(['The selected time window has no records in this CSV. ' ...
               'Set useTimeWindow = false to display the complete file.']);
    end
end
t = t(keep); node = node(keep); y = y(keep);
if isempty(t) || ~any(isfinite(y))
    error('The selected records have no finite pressure_hpa values. Check the pressure column.');
end

colors = [0.000 0.447 0.741; ...
          0.850 0.325 0.098; ...
          0.200 0.600 0.200; ...
          0.700 0.150 0.650];
fig = figure('Name', ['Pressure - ' file], 'NumberTitle', 'off', ...
    'Color', 'w', 'Position', [100 100 1250 700], ...
    'Resize', 'on', 'ToolBar', 'figure');
ax = axes('Parent', fig, 'Position', [0.08 0.17 0.88 0.74]);
hold(ax, 'on');
handles = gobjects(0);

for k = 1:numel(names)
    idx = node == names(k);
    if ~any(idx)
        warning('Missing sensor: %s', char(names(k)));
        continue;
    end
    tn = t(idx); yn = y(idx);
    [tn, order] = sort(tn);
    yn = yn(order);
    gap = find(seconds(diff(tn)) > 30);
    if ~isempty(gap)
        tn = [tn; tn(gap) + milliseconds(1)];
        yn = [yn; nan(numel(gap),1)];
        [tn, order] = sort(tn);
        yn = yn(order);
    end
    handles(end+1) = plot(ax, tn, yn, '-', 'Color', colors(k,:), ...
        'LineWidth', 1, 'DisplayName', char(names(k))); %#ok<AGROW>
    fprintf('%s: %d finite pressure points\n', ...
        char(names(k)), sum(isfinite(yn)));
end

grid(ax, 'on'); box(ax, 'on');
ax.FontSize = 11;
xlabel(ax, 'Receive time');
ylabel(ax, 'Pressure (hPa)');
title(ax, 'Multi-node Pressure Measurements');
legend(ax, handles, 'Location', 'best', 'Interpreter', 'none');
xtickformat(ax, 'MM-dd HH:mm:ss');
xtickangle(ax, 25);

fullX = [min(t), max(t)];
if fullX(1) == fullX(2)
    fullX = fullX + seconds([-1 1]);
end
finiteY = y(isfinite(y));
low = min(finiteY);
high = max(finiteY);
padding = max(0.1, 0.05 * (high - low));
fullY = [low-padding, high+padding];
xlim(ax, fullX); ylim(ax, fullY);

uicontrol(fig, 'Style', 'pushbutton', 'String', 'Zoom', ...
    'Units', 'normalized', 'Position', [0.08 0.025 0.11 0.05], ...
    'Callback', @(~,~) zoom(fig, 'on'));
uicontrol(fig, 'Style', 'pushbutton', 'String', 'Pan', ...
    'Units', 'normalized', 'Position', [0.20 0.025 0.11 0.05], ...
    'Callback', @(~,~) pan(fig, 'on'));
uicontrol(fig, 'Style', 'pushbutton', 'String', 'Full view', ...
    'Units', 'normalized', 'Position', [0.32 0.025 0.13 0.05], ...
    'Callback', @(~,~) set(ax, 'XLim', fullX, 'YLim', fullY));
uicontrol(fig, 'Style', 'text', ...
    'String', 'Zoom: scroll / select area     Pan: click and drag', ...
    'Units', 'normalized', 'Position', [0.47 0.025 0.49 0.04], ...
    'BackgroundColor', 'w', 'HorizontalAlignment', 'left');
zoom(fig, 'on');
drawnow;
fprintf('Done: %d sensor curves displayed. Use Zoom, Pan or Full view.\n', numel(handles));
end
