"use client";

import { Autocomplete } from "@react-google-maps/api";
import { TextInput, Button, Group } from "@mantine/core";
import { useState, useRef } from "react";

interface Props {
  onPlaceSelected: (lat: number, lng: number, address: string) => void;
  loading?: boolean;
}

export default function AddressSearch({ onPlaceSelected, loading }: Props) {
  const [value, setValue] = useState("");
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);

  const onLoad = (autocomplete: google.maps.places.Autocomplete) => {
    autocompleteRef.current = autocomplete;
  };

  const onPlaceChanged = () => {
    const place = autocompleteRef.current?.getPlace();
    if (place?.geometry?.location) {
      const lat = place.geometry.location.lat();
      const lng = place.geometry.location.lng();
      const address = place.formatted_address || value;
      setValue(address);
      onPlaceSelected(lat, lng, address);
    }
  };

  return (
    <Group align="end" gap="sm">
      <Autocomplete
        onLoad={onLoad}
        onPlaceChanged={onPlaceChanged}
        options={{
          componentRestrictions: { country: "au" },
          types: ["address"],
        }}
      >
        <TextInput
          label="Your address"
          placeholder="e.g. 42 Wallaby Way, Sydney NSW"
          value={value}
          onChange={(e) => setValue(e.currentTarget.value)}
          style={{ minWidth: 380 }}
        />
      </Autocomplete>
      <Button loading={loading} disabled={!value} onClick={onPlaceChanged}>
        Search
      </Button>
    </Group>
  );
}
