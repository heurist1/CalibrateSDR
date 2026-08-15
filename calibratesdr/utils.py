import numpy as np
from scipy.fftpack import fft, fftshift, ifft
import matplotlib.pyplot as plt
import calibratesdr as cali

def movingaverage (values, window):
    weights = np.repeat(1.0, window)/window
    sma = np.convolve(values, weights, 'same')
    return sma

def reduce_outliers(dif):

    limit_b4 = 0.0
    limit_set = 1.0
    std_factor = 3.0
    counter = 0

    while limit_b4 - np.std(dif) * std_factor != 0 and \
            limit_set < np.std(dif) * std_factor and \
            counter < 20 and np.std(dif) != 0:

        std = np.std(dif)
        meany = np.mean(dif)

        limit = std * std_factor

        for j in range(len(dif)):

            if np.abs(dif[j] - meany) >= limit:
                #print("pop", counter, j, np.abs(dif[j] - meany), limit)
                dif = np.delete(dif, j)
                break

        limit_b4 = limit
        counter += 1

    return dif


def load_data(filename, offset):
    samples = np.memmap(filename, offset=offset)
    return samples


def signal_bar(snr, snr_max):
    bar_length = 20

    if snr_max != 0:
        percent = snr / snr_max
    else:
        percent = 0.0

    hashes = '#' * int(round(percent * bar_length))
    spaces = ' ' * (bar_length - len(hashes))

    bar = "[{0}] {1}%".format(hashes + spaces, int(round(percent * 100)))

    return bar


def get_fft(data, samplerate = 2048000):
    adc_offset = -127

    signal_fft = []
    window = samplerate

    for slice in range(0, int(len(data) // (window * 2)) * window * 2, window * 2):
        # FIX: .astype(float) needed before adding int to uint8 array to avoid overflow error
        data_slice = (adc_offset + data[slice: slice + window * 2: 2].astype(float)) +\
                      1j * (adc_offset + data[slice + 1: slice + window * 2: 2].astype(float))


        norm_fft = (1.0 / window) * fftshift(fft(data_slice))
        abs_fft = np.abs(norm_fft)

        transform = 10 * np.log10(abs_fft / np.abs(adc_offset))

        signal_fft.append(transform)

    return signal_fft


def record_with_rtlsdr(sdr, rs, cf, ns, rg, filename, offset=0):

    sdr.rs = rs
    # FIX: optional offset tuning. Some tuners (e.g. Fitipower FC0013) have a strong
    # noise spike around DC. Tuning to cf + offset moves that spike out of the DAB band
    # so the null symbol / phase reference detection in get_ppm() works. The PPM value
    # is derived from the sample-rate (crystal) error, so it is unaffected by the offset.
    sdr.fc = cf + offset
    sdr.gain = rg

    # FIX: Use read_samples() instead of read_bytes_async() for compatibility with some R828D-based devices.
    # read_bytes_async() uses rtlsdr_read_async() which queues 32 concurrent USB transfers.
    # Some R828D dongles (e.g. certain no bias-T variants) return LIBUSB_ERROR_BUSY (-6) on
    # these concurrent transfers, causing I2C errors and an access violation crash in rtlsdr_close().
    # read_samples() uses rtlsdr_read_sync() which issues a single blocking USB read with no
    # concurrency issues. The complex float output is converted back to uint8 IQ for file compatibility.
    samples = sdr.read_samples(ns)
    raw_i = np.clip(np.round(samples.real * 127 + 127), 0, 255).astype(np.uint8)
    raw_q = np.clip(np.round(samples.imag * 127 + 127), 0, 255).astype(np.uint8)

    interleaved = np.empty(len(samples) * 2, dtype=np.uint8)
    interleaved[0::2] = raw_i
    interleaved[1::2] = raw_q

    interleaved.tofile(filename)

def scan_one_dab_channel(dabchannels, channel, sdr, rs, ns, rg, filename, samplerate, show_graph, verbose, offset=0):

    cf = dabchannels["dab"][channel]["f_center"]
    block = dabchannels["dab"][channel]["block"]

    record_with_rtlsdr(sdr, rs, cf, ns, rg, filename, offset)

    data = load_data(filename, offset=0)
    dab_ppm = cali.dabplus.dab.get_ppm(data, samplerate=samplerate, show_graph=show_graph, verbose=verbose)

    dab_signal_fft = get_fft(data, samplerate=samplerate)

    dab_signal_fft_mean = np.mean(dab_signal_fft, axis=0)
    dab_signal_bins = cali.dabplus.dab.signal_level(dab_signal_fft_mean, 200)
    dab_snr = cali.dabplus.dab.signal_dynamics(dab_signal_bins, 12)

    if show_graph == True:
        plt.plot(dab_signal_bins)
        plt.grid()
        plt.title("dab block shape")
        plt.xlabel("sample bin")
        plt.ylabel("amplitude")
        plt.show()

    limit_db = 2.0
    dab_block_detected = cali.dabplus.dab.block_check(dab_signal_bins, dab_snr, limit_db=limit_db)

    del data

    return channel, block, cf, dab_snr, dab_block_detected, dab_ppm